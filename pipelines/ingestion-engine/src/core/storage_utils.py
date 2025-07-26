import io
from typing import Dict, List

import polars as pl
from google.cloud import storage

from core.logging_utils import get_logger, log

logger = get_logger(__name__)


def json_to_polars(data: List[Dict], lazy: bool = False) -> pl.DataFrame | pl.LazyFrame:
    """
    Convert JSON data to a Polars DataFrame.

    Args:
        data (List[Dict]): List of dictionaries representing JSON data.
        lazy (bool): If True, returns a Polars LazyFrame; otherwise, returns a DataFrame.

    Returns:
        pl.DataFrame: Polars DataFrame containing the data
        or
        pl.LzyFrame: Polars LazyFrame containing the data if lazy is True
    """
    log(
        logger,
        "INFO",
        f"Converting JSON to {'LazyFrame' if lazy else 'DataFrame'}",
        name="json_to_polars",
    )
    df = pl.DataFrame(data)
    log(logger, "SUCCESS", f"Converted {len(df)} rows", name="json_to_polars")
    return df.lazy() if lazy else df


def polars_to_parquet_bytes(df: pl.DataFrame | pl.LazyFrame) -> bytes:
    """
    Convert Polars DataFrame to Parquet bytes

    Args:
        df (pl.Dataframe | pl.LazyFrame): Data to convert to parquet bytes
    Returns:
        bytes: Parquet bytes containing data
    """
    if isinstance(df, pl.LazyFrame):
        log(
            logger,
            "INFO",
            "Collecting LazyFrame into DataFrame",
            name="polars_to_parquet_bytes",
        )
        df = df.collect()
    buffer = io.BytesIO()
    df.write_parquet(buffer)
    buffer.seek(0)
    log(
        logger, "SUCCESS", "Parquet conversion complete", name="polars_to_parquet_bytes"
    )
    return buffer.read()


def upload_bytes_to_gcs(bucket_name: str, dest_path: str, data_bytes: bytes) -> None:
    """
    Upload bytes to Google Cloud Storage.

    Args:
        bucket_name (str): Name of the GCS bucket.
        dest_path (str): Destination path in the bucket.
        data_bytes (bytes): Data to upload as bytes.
    """
    log(
        logger,
        "INFO",
        f"Uploading to gs://{bucket_name}/{dest_path}",
        name="upload_bytes_to_gcs",
    )
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(dest_path)
    blob.upload_from_string(data_bytes)
    log(
        logger,
        "SUCCESS",
        f"Upload complete: gs://{bucket_name}/{dest_path}",
        name="upload_bytes_to_gcs",
    )
