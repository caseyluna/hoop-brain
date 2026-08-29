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
    mock_get_teams.return_value = [
        {"id": 1, "full_name": "Team A"},
        {"id": 2, "full_name": "Team B"},
    ]
    client = NBAApi(bucket="hoop-brain-raw-data")

    client.ingest_teams()

    mock_load_to_bq.assert_called_once_with(filename="teams")
    mock_upload.assert_called_once()
    _, kwargs = mock_upload.call_args
    assert kwargs["filename"] == "teams"
    assert all(team["league"] == "NBA" for team in kwargs["data"])


@patch.object(NBAApi, "load_to_bq")
@patch.object(NBAApi, "upload")
@patch.object(NBAApi, "get_teams")
def test_ingest_teams_tags_every_record_with_nba_league(
    mock_get_teams, mock_upload, mock_load_to_bq
):
    mock_get_teams.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]
    client = NBAApi(bucket="hoop-brain-raw-data")

    client.ingest_teams()

    _, kwargs = mock_upload.call_args
    leagues = [team["league"] for team in kwargs["data"]]
    assert leagues == ["NBA", "NBA", "NBA"]
