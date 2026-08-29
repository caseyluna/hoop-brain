from unittest.mock import patch

from modules.nba_api import NBAApi


@patch("modules.nba_api.load_parquet_from_gcs")
def test_load_to_bq_builds_correct_uri_and_dataset(mock_load):
    client = NBAApi(bucket="hoop-brain-raw-data", base_path="nba-api", vendor="nba_api")

    client.load_to_bq(filename="teams")

    mock_load.assert_called_once_with(
        gcs_uri="gs://hoop-brain-raw-data/nba-api/teams.parquet",
        dataset="raw_nba_api",
        table="teams",
    )


@patch.object(NBAApi, "load_to_bq")
@patch.object(NBAApi, "upload")
@patch.object(NBAApi, "get_teams")
def test_ingest_teams_uploads_then_loads(mock_get_teams, mock_upload, mock_load_to_bq):
    mock_get_teams.return_value = [{"id": 1, "full_name": "Team A"}]
    client = NBAApi(bucket="hoop-brain-raw-data")

    client.ingest_teams()

    mock_upload.assert_called_once_with(
        data=mock_get_teams.return_value, filename="teams"
    )
    mock_load_to_bq.assert_called_once_with(filename="teams")
