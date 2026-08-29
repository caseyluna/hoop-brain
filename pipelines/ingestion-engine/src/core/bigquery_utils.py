from google.cloud import bigquery

from core.logging_utils import get_logger, log

logger = get_logger(__name__)


def load_parquet_from_gcs(gcs_uri: str, dataset: str, table: str) -> None:
    """
    Load a Parquet file from GCS into a BigQuery table, replacing any existing rows.

    Creates the destination dataset if it doesn't already exist. The destination
    table is created automatically by the load job (schema comes from the Parquet
    file itself) if it doesn't already exist.

    Args:
        gcs_uri (str): GCS URI of the Parquet file (e.g. gs://bucket/path/file.parquet).
        dataset (str): Destination BigQuery dataset (e.g. raw_nba_api).
        table (str): Destination BigQuery table name.
    """
    destination = f"{dataset}.{table}"
    log(
        logger,
        "INFO",
        f"Loading {gcs_uri} -> {destination}",
        name="load_parquet_from_gcs",
    )
    client = bigquery.Client()
    client.create_dataset(dataset, exists_ok=True)

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    load_job = client.load_table_from_uri(gcs_uri, destination, job_config=job_config)
    load_job.result()

    log(
        logger,
        "SUCCESS",
        f"Loaded {load_job.output_rows} rows into {destination}",
        name="load_parquet_from_gcs",
    )
