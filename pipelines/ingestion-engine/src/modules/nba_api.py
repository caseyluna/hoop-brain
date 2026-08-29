from typing import Dict, List

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
        Ingests NBA teams data, uploads it to GCS, and loads it into BigQuery.
        """
        teams_data = self.get_teams()
        log(logger, "SUCCESS", "Retrieved NBA teams successfully", name="NBAApi")
        self.upload(data=teams_data, filename="teams")
        self.load_to_bq(filename="teams")
