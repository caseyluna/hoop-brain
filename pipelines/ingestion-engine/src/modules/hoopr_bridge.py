import sys
from pathlib import Path

import polars as pl

from core.bigquery_utils import load_parquet_from_gcs
from core.logging_utils import get_logger, log
from core.storage_utils import polars_to_parquet_bytes, upload_bytes_to_gcs

logger = get_logger(__name__)


class HoopRBridge:
    """
    Picks up CSV output written by the hoopR/wehoop R utility (pipelines/ingestion-engine/r,
    CAL-252) and carries it through the same GCS -> BigQuery raw path every other ingestion
    source uses. R never talks to GCS/BigQuery directly - Python stays the single point of
    contact with our infra; R's only job is running the hoopR/wehoop function and writing its
    output to a shared path that this class then reads from disk.
    """

    def __init__(self, bucket: str, base_path: str = "hoopr", vendor: str = "hoopr"):
        self.bucket = bucket
        self.base_path = base_path
        self.vendor = vendor

    def upload(self, csv_path: Path, filename: str) -> None:
        """
        Reads a CSV written by the R utility and uploads it to GCS as Parquet, matching
        the format every other ingestion source's upload() already produces.
        """
        log(logger, "INFO", f"Reading R output from {csv_path}", name="HoopRBridge")
        df = pl.read_csv(csv_path)
        parquet_bytes = polars_to_parquet_bytes(df)
        dest_path = f"{self.base_path}/{filename}.parquet"
        upload_bytes_to_gcs(
            bucket_name=self.bucket, dest_path=dest_path, data_bytes=parquet_bytes
        )
        log(
            logger,
            "SUCCESS",
            f"Uploaded '{filename}.parquet' to bucket '{self.bucket}'",
            name="HoopRBridge",
        )

    def load_to_bq(self, filename: str) -> None:
        """
        Loads a previously-uploaded Parquet file from GCS into this vendor's raw
        BigQuery dataset (raw_<vendor>.<filename>).
        """
        log(logger, "INFO", f"Loading '{filename}' into BigQuery", name="HoopRBridge")
        gcs_uri = f"gs://{self.bucket}/{self.base_path}/{filename}.parquet"
        dataset = f"raw_{self.vendor}"
        load_parquet_from_gcs(gcs_uri=gcs_uri, dataset=dataset, table=filename)
        log(
            logger,
            "SUCCESS",
            f"Loaded '{filename}.parquet' into '{dataset}.{filename}'",
            name="HoopRBridge",
        )

    def ingest_csv(self, csv_path: Path, filename: str) -> None:
        """
        Full pipeline for one R-produced CSV: GCS upload -> BQ load.
        """
        self.upload(csv_path=csv_path, filename=filename)
        self.load_to_bq(filename=filename)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: hoopr_bridge.py <csv_path> <filename>")
    bucket = "hoop-brain-raw-data"
    client = HoopRBridge(bucket=bucket)
    client.ingest_csv(csv_path=Path(sys.argv[1]), filename=sys.argv[2])


if __name__ == "__main__":
    main()
