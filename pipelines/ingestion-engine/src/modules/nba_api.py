from typing import Dict, List, Optional

from nba_api.stats.endpoints import LeagueDashPlayerBioStats
from nba_api.stats.static import players, teams

from core.bigquery_utils import load_parquet_from_gcs
from core.logging_utils import get_logger, log
from core.performance_utils import PerfTracker
from core.storage_utils import (
    json_to_polars,
    polars_to_parquet_bytes,
    upload_bytes_to_gcs,
)

logger = get_logger(__name__)


class NBAApi:
    """
    A client for interacting with the NBA API to fetch raw data, uploading it to GCS
    as optimized Parquet files, and loading it into BigQuery raw_<vendor> tables.

    Birthdate handling (Player ingestion, CAL-147): nba_api has no bulk source for
    player birthdate. The static `players.get_players()` index (used by
    `get_players()`) carries no bio fields at all, and the league-wide bulk bio
    endpoint (`LeagueDashPlayerBioStats`, used by `get_player_bio_stats()`) exposes
    AGE but not birthdate for anyone -- active or historical. The only nba_api path
    to a real birthdate is `CommonPlayerInfo`, a per-player call with no bulk
    equivalent (~5,000 requests to cover the full historical index). That per-player
    backfill is deliberately out of scope here and deferred to a future ticket,
    scoped once Tier-2 entity matching (ADR 001) is actually being built -- the same
    call CAL-159 made independently for WNBA player ingestion, which hit the same
    "no bulk birthdate source" gap for its league.
    """

    def __init__(
        self, bucket: str, base_path: str = "nba-api", vendor: str = "nba_api"
    ):
        self.bucket = bucket
        self.base_path = base_path
        self.vendor = vendor

    @staticmethod
    @PerfTracker.decorator("Fetch NBA Teams")
    def get_teams() -> List[Dict]:
        """
        Fetches the list of NBA teams.
        Returns:
            list[dict]: A list of dictionaries containing team information.
        """
        log(logger, "INFO", "Fetching NBA teams...", name="NBAApi")
        return teams.get_teams()

    @staticmethod
    @PerfTracker.decorator("Fetch NBA Players")
    def get_players() -> List[Dict]:
        """
        Fetches the list of NBA players.
        Returns:
            list[dict]: A list of dictionaries containing player information.
        """
        log(logger, "INFO", "Fetching NBA players...", name="NBAApi")
        return players.get_players()

    @staticmethod
    @PerfTracker.decorator("Fetch NBA Player Bio Stats")
    def get_player_bio_stats(
        season: Optional[str] = None, timeout: int = 60
    ) -> List[Dict]:
        """
        Fetches league-wide player bio/roster attributes (current team, age, height,
        weight, college, country, draft info) for a single season via nba_api's
        LeagueDashPlayerBioStats -- a live, season-scoped bulk endpoint, unlike the
        static index `get_players()` reads from.

        Only covers players who appeared in the given season, and does NOT include
        birthdate (only AGE) -- see this class's docstring for how that gap is
        handled.

        Args:
            season (str | None): Season string, e.g. "2025-26". Defaults to
                nba_api's own current-season default (`Season.default`).
            timeout (int): Request timeout in seconds. nba_api's own default (30s)
                isn't reliably enough for this endpoint in practice -- it's one of
                stats.nba.com's heavier server-side aggregations across the full
                league -- so this defaults higher.
        Returns:
            list[dict]: One row per player with that season's bio/roster attributes.
        """
        log(logger, "INFO", "Fetching NBA player bio stats...", name="NBAApi")
        kwargs = {"season": season} if season else {}
        endpoint = LeagueDashPlayerBioStats(timeout=timeout, **kwargs)
        return endpoint.get_normalized_dict()["LeagueDashPlayerBioStats"]

    @PerfTracker.decorator("Upload Data to GCS")
    def upload(self, data: List[Dict], filename: str, lazy: bool = False) -> None:
        """
        Uploads data to the specified bucket in JSON format.
        Args:
            data (List[Dict]): The data to upload.
            filename (str): The name of the file to save the data as.
            lazy (bool): If True, the data will be processed lazily.
        """
        log(logger, "INFO", f"Preparing raw data for upload: {filename}", name="NBAApi")

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
            name="NBAApi",
        )

    @PerfTracker.decorator("Load Data to BigQuery")
    def load_to_bq(self, filename: str) -> None:
        """
        Loads a previously-uploaded Parquet file from GCS into this vendor's raw
        BigQuery dataset (raw_<vendor>.<filename>).
        Args:
            filename (str): Base filename (without extension) previously uploaded via `upload()`.
        """
        log(logger, "INFO", f"Loading '{filename}' into BigQuery", name="NBAApi")
        gcs_uri = f"gs://{self.bucket}/{self.base_path}/{filename}.parquet"
        dataset = f"raw_{self.vendor}"
        load_parquet_from_gcs(gcs_uri=gcs_uri, dataset=dataset, table=filename)
        log(
            logger,
            "SUCCESS",
            f"Loaded '{filename}.parquet' into '{dataset}.{filename}'",
            name="NBAApi",
        )

    @PerfTracker.decorator("Ingest NBA Teams")
    def ingest_teams(self) -> None:
        """
        Ingests NBA teams data, tags it with league, uploads it to GCS, and loads
        it into BigQuery.
        """
        teams_data = self.get_teams()
        log(logger, "SUCCESS", "Retrieved NBA teams successfully", name="NBAApi")
        # nba_api is NBA-only by definition; the WNBA adapter tags its own records.
        for team in teams_data:
            team["league"] = "NBA"
        self.upload(data=teams_data, filename="teams")
        self.load_to_bq(filename="teams")

    @PerfTracker.decorator("Ingest NBA Players")
    def ingest_players(self, season: Optional[str] = None) -> None:
        """
        Ingests the full historical + active NBA player index (nba_api's static
        `players` list, which covers every player ever and flags `is_active`),
        enriches it with current-season bio/roster attributes (team, age, height,
        weight, college, country, draft info) from `LeagueDashPlayerBioStats`, tags
        it with league, uploads it to GCS, and loads it into BigQuery.

        Only players who appeared in `season` get bio attributes attached; everyone
        else (retired/historical players, or active players who haven't played yet
        this season) gets those fields as null -- expected, not a data-quality bug.
        Birthdate is not included; see this class's docstring.

        Args:
            season (str | None): Season passed through to `get_player_bio_stats()`.
        """
        players_data = self.get_players()
        log(logger, "SUCCESS", "Retrieved NBA players successfully", name="NBAApi")

        # Bio enrichment is supplementary (see class docstring: no bulk birthdate
        # source exists anyway) and depends on a single live stats.nba.com call
        # that's known to be flaky/rate-limited outside NBA's own infra. A failure
        # here must not block landing the core player index -- that's this
        # ticket's primary deliverable -- so it degrades to unenriched records
        # (every bio field null) rather than failing the whole ingest.
        try:
            bio_stats = self.get_player_bio_stats(season=season)
            log(
                logger,
                "SUCCESS",
                "Retrieved NBA player bio stats successfully",
                name="NBAApi",
            )
            bio_by_id = {row["PLAYER_ID"]: row for row in bio_stats}
        except Exception as exc:
            log(
                logger,
                "WARNING",
                f"Failed to fetch NBA player bio stats ({exc!r}); landing players "
                "without bio enrichment for this run -- team/age/height/weight/"
                "college/country/draft fields will be null for every player.",
                name="NBAApi",
            )
            bio_by_id = {}

        # nba_api is NBA-only by definition; the WNBA adapter tags its own records.
        for player in players_data:
            player["league"] = "NBA"
            bio = bio_by_id.get(player["id"])
            player["team_id"] = bio["TEAM_ID"] if bio else None
            player["team_abbreviation"] = bio["TEAM_ABBREVIATION"] if bio else None
            player["age"] = bio["AGE"] if bio else None
            player["height"] = bio["PLAYER_HEIGHT"] if bio else None
            player["height_inches"] = bio["PLAYER_HEIGHT_INCHES"] if bio else None
            player["weight"] = bio["PLAYER_WEIGHT"] if bio else None
            player["college"] = bio["COLLEGE"] if bio else None
            player["country"] = bio["COUNTRY"] if bio else None
            player["draft_year"] = bio["DRAFT_YEAR"] if bio else None
            player["draft_round"] = bio["DRAFT_ROUND"] if bio else None
            player["draft_number"] = bio["DRAFT_NUMBER"] if bio else None

        self.upload(data=players_data, filename="players")
        self.load_to_bq(filename="players")
