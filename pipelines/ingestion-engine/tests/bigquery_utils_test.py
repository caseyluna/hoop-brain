from unittest.mock import MagicMock, patch

from core.bigquery_utils import load_parquet_from_gcs


@patch("core.bigquery_utils.bigquery.Client")
def test_load_parquet_from_gcs_creates_dataset_and_loads_table(mock_client_cls):
    mock_client = MagicMock()
    mock_load_job = MagicMock()
    mock_load_job.output_rows = 3
    mock_client.load_table_from_uri.return_value = mock_load_job
    mock_client_cls.return_value = mock_client

    load_parquet_from_gcs(
        gcs_uri="gs://bucket/nba-api/teams.parquet",
        dataset="raw_nba_api",
        table="teams",
    )

    mock_client.create_dataset.assert_called_once_with("raw_nba_api", exists_ok=True)

    args, kwargs = mock_client.load_table_from_uri.call_args
    assert args[0] == "gs://bucket/nba-api/teams.parquet"
    assert args[1] == "raw_nba_api.teams"
    job_config = kwargs["job_config"]
    assert job_config.source_format == "PARQUET"
    assert job_config.write_disposition == "WRITE_TRUNCATE"

    mock_load_job.result.assert_called_once()
