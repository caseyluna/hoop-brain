from pathlib import Path
from typing import Dict, List

import polars as pl
import requests

from core.bigquery_utils import load_parquet_from_gcs
from core.logging_utils import get_logger, log
from core.performance_utils import PerfTracker
from core.storage_utils import (
    json_to_polars,
    polars_to_parquet_bytes,
    upload_bytes_to_gcs,
)

logger = get_logger(__name__)

# ESPN's public WNBA teams endpoint — the same one sportsdataverse's
# espn_wnba_teams() wraps. No API key, no rate limit published. stats.wnba.com
# (the other half of the "wehoop" source family) has no equivalent static
# team-directory endpoint — its endpoints are all game/box/roster data keyed
# off a season, so ESPN is the source for the team list itself.
ESPN_WNBA_TEAMS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams"
)


def _na(value):
    """
    R's readr::write_csv (used by the shared R-invocation utility, CAL-252) writes
    missing values as the literal string "NA", not an empty cell -- so every column
    from an R-produced CSV, numeric or not, can come back as the string "NA" rather
    than a real null. Normalize that (and empty/whitespace-only strings) to None.
    """
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped and stripped != "NA" else None
    return value


def _int(value):
    """Like `_na`, but coerces to int when a real value is present."""
    cleaned = _na(value)
    return int(cleaned) if cleaned is not None else None


class WNBAApi:
    """
    A client for interacting with WNBA data sources (currently ESPN's public
    teams endpoint, part of the wehoop/sportsdataverse source family) to fetch
    raw data, uploading it to GCS as optimized Parquet files, and loading it
    into BigQuery raw_<vendor> tables.
    """

    def __init__(self, bucket: str, base_path: str = "wehoop", vendor: str = "wehoop"):
        self.bucket = bucket
        self.base_path = base_path
        self.vendor = vendor

    @staticmethod
    @PerfTracker.decorator("Fetch WNBA Teams")
    def get_teams() -> List[Dict]:
        """
        Fetches the list of WNBA teams from ESPN's public teams endpoint.

        ESPN doesn't publish `state` or `year_founded` for WNBA teams the way
        nba_api's static teams module does for NBA teams, so those two fields
        come back None — stg_wehoop__teams still selects them (as null) so the
        marts.teams UNION ALL with stg_nba_api__teams lines up column-for-column.

        Returns:
            list[dict]: A list of dictionaries containing team information.
        """
        log(logger, "INFO", "Fetching WNBA teams...", name="WNBAApi")
        resp = requests.get(ESPN_WNBA_TEAMS_URL, params={"limit": 1000}, timeout=30)
        resp.raise_for_status()
        leagues = resp.json()["sports"][0]["leagues"]
        raw_teams = [entry["team"] for entry in leagues[0]["teams"]]
        return [
            {
                "id": int(team["id"]),
                "full_name": team["displayName"],
                "abbreviation": team["abbreviation"],
                "nickname": team["name"],
                "city": team["location"],
                "state": None,
                "year_founded": None,
            }
            for team in raw_teams
        ]

    @staticmethod
    @PerfTracker.decorator("Read WNBA Players")
    def get_players(csv_path: Path) -> List[Dict]:
        """
        Reads the CSV written by `wehoop::wnba_playerindex()` (pulled separately via the
        shared R-invocation utility, pipelines/ingestion-engine/r, CAL-252/CAL-159) and
        reshapes it into our player record schema.

        Design note: `wnba_playerindex()` is the confirmed wehoop equivalent of hoopR's
        `nba_playerindex()` (verified against wehoop's pkgdown reference and a real pull —
        26 columns, ~1200 rows, all-time roster since `historical=1` is the default). It
        does **not** return a birthdate column. `wnba_commonteamroster()` does (BIRTH_DATE),
        but only per-team, which would mean looping over ~13 team IDs and joining — real
        extra scope this ticket doesn't need, since the Tier-2 resolver step that would
        consume birthdate is itself blocked on CAL-148/150. Landing player-index without
        birthdate now, flagged here, keeps this ticket to its one-function scope; a
        birthdate backfill via commonteamroster is a candidate follow-up once the resolver
        actually gets built.

        Args:
            csv_path (Path): Path to the CSV written by the R utility.

        Returns:
            list[dict]: A list of dictionaries containing player information.
        """
        log(
            logger,
            "INFO",
            f"Reading WNBA player index from {csv_path}",
            name="WNBAApi",
        )
        df = pl.read_csv(csv_path, infer_schema_length=None)
        records = df.to_dicts()
        players = []
        for row in records:
            first_name = _na(row.get("PLAYER_FIRST_NAME"))
            last_name = _na(row.get("PLAYER_LAST_NAME"))
            full_name = " ".join(n for n in (first_name, last_name) if n) or None
            players.append(
                {
                    "id": _int(row["PERSON_ID"]),
                    "first_name": first_name,
                    "last_name": last_name,
                    "full_name": full_name,
                    "team_id": _int(row.get("TEAM_ID")),
                    "team_city": _na(row.get("TEAM_CITY")),
                    "team_name": _na(row.get("TEAM_NAME")),
                    "team_abbreviation": _na(row.get("TEAM_ABBREVIATION")),
                    "jersey_number": _na(row.get("JERSEY_NUMBER")),
                    "position": _na(row.get("POSITION")),
                    "height": _na(row.get("HEIGHT")),
                    "weight": _int(row.get("WEIGHT")),
                    "college": _na(row.get("COLLEGE")),
                    "country": _na(row.get("COUNTRY")),
                    "draft_year": _int(row.get("DRAFT_YEAR")),
                    "draft_round": _int(row.get("DRAFT_ROUND")),
                    "draft_number": _int(row.get("DRAFT_NUMBER")),
                    "roster_status": _na(row.get("ROSTER_STATUS")),
                    "from_year": _int(row.get("FROM_YEAR")),
                    "to_year": _int(row.get("TO_YEAR")),
                }
            )
        return players

    @PerfTracker.decorator("Upload Data to GCS")
    def upload(self, data: List[Dict], filename: str, lazy: bool = False) -> None:
        """
        Uploads data to the specified bucket in JSON format.
        Args:
            data (List[Dict]): The data to upload.
            filename (str): The name of the file to save the data as.
            lazy (bool): If True, the data will be processed lazily.
        """
        log(
            logger, "INFO", f"Preparing raw data for upload: {filename}", name="WNBAApi"
        )

        df = json_to_polars(data=data, lazy=lazy)
        parquet_bytes = polars_to_parquet_bytes(df)
        dest_path = f"{self.base_path}/{filename}.parquet"
        upload_bytes_to_gcs(
            bucket_name=self.bucket, dest_path=dest_path, data_bytes=parquet_bytes
        )
        log(
            logger,
            "SUCCESS",
            f"Uploaded '{filename}.parquet to bucket '{self.bucket}'",
            name="WNBAApi",
        )

    @PerfTracker.decorator("Load Data to BigQuery")
    def load_to_bq(self, filename: str) -> None:
        """
        Loads a previously-uploaded Parquet file from GCS into this vendor's raw
        BigQuery dataset (raw_<vendor>.<filename>).
        Args:
            filename (str): Base filename (without extension) previously uploaded via `upload()`.
        """
        log(logger, "INFO", f"Loading '{filename}' into BigQuery", name="WNBAApi")
        gcs_uri = f"gs://{self.bucket}/{self.base_path}/{filename}.parquet"
        dataset = f"raw_{self.vendor}"
        load_parquet_from_gcs(gcs_uri=gcs_uri, dataset=dataset, table=filename)
        log(
            logger,
            "SUCCESS",
            f"Loaded '{filename}.parquet' into '{dataset}.{filename}'",
            name="WNBAApi",
        )

    @PerfTracker.decorator("Ingest WNBA Teams")
    def ingest_teams(self) -> None:
        """
        Ingests WNBA teams data, tags it with league, uploads it to GCS, and
        loads it into BigQuery.
        """
        teams_data = self.get_teams()
        log(logger, "SUCCESS", "Retrieved WNBA teams successfully", name="WNBAApi")
        # the WNBA adapter tags its own records; nba_api tags its own as NBA.
        for team in teams_data:
            team["league"] = "WNBA"
        self.upload(data=teams_data, filename="teams")
        self.load_to_bq(filename="teams")

    @PerfTracker.decorator("Ingest WNBA Players")
    def ingest_players(self, csv_path: Path) -> None:
        """
        Ingests the WNBA player index (pulled via `wehoop::wnba_playerindex()` ahead of
        this call, see `task ingestion:r-wnba-players`), tags it with league, uploads it
        to GCS, and loads it into BigQuery (`raw_wehoop.players`).

        Source player IDs (`PERSON_ID`) go through the Tier-1 resolver as their own
        authoritative source (`source="wehoop"`) once the resolver exists (CAL-148/150) —
        never matched against `nba_api` rows. This step only lands the raw data.

        Args:
            csv_path (Path): Path to the CSV written by the R utility for this pull.
        """
        players_data = self.get_players(csv_path=csv_path)
        log(logger, "SUCCESS", "Retrieved WNBA players successfully", name="WNBAApi")
        # the WNBA adapter tags its own records; nba_api tags its own as NBA.
        for player in players_data:
            player["league"] = "WNBA"
        self.upload(data=players_data, filename="players")
        self.load_to_bq(filename="players")
