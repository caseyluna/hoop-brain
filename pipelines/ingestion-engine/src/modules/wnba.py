from typing import Dict, List

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
