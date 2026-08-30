from unittest.mock import Mock, patch

from modules.wnba import WNBAApi


@patch("modules.wnba.load_parquet_from_gcs")
def test_load_to_bq_builds_correct_uri_and_dataset(mock_load):
    client = WNBAApi(bucket="hoop-brain-raw-data", base_path="wehoop", vendor="wehoop")

    client.load_to_bq(filename="teams")

    mock_load.assert_called_once_with(
        gcs_uri="gs://hoop-brain-raw-data/wehoop/teams.parquet",
        dataset="raw_wehoop",
        table="teams",
    )


@patch("modules.wnba.requests.get")
def test_get_teams_parses_espn_response(mock_get):
    mock_get.return_value = Mock(
        status_code=200,
        json=lambda: {
            "sports": [
                {
                    "leagues": [
                        {
                            "teams": [
                                {
                                    "team": {
                                        "id": "17",
                                        "displayName": "Las Vegas Aces",
                                        "abbreviation": "LV",
                                        "name": "Aces",
                                        "location": "Las Vegas",
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        },
    )

    teams = WNBAApi.get_teams()

    assert teams == [
        {
            "id": 17,
            "full_name": "Las Vegas Aces",
            "abbreviation": "LV",
            "nickname": "Aces",
            "city": "Las Vegas",
            "state": None,
            "year_founded": None,
        }
    ]


@patch.object(WNBAApi, "load_to_bq")
@patch.object(WNBAApi, "upload")
@patch.object(WNBAApi, "get_teams")
def test_ingest_teams_uploads_then_loads(mock_get_teams, mock_upload, mock_load_to_bq):
    mock_get_teams.return_value = [
        {"id": 1, "full_name": "Team A"},
        {"id": 2, "full_name": "Team B"},
    ]
    client = WNBAApi(bucket="hoop-brain-raw-data")

    client.ingest_teams()

    mock_load_to_bq.assert_called_once_with(filename="teams")
    mock_upload.assert_called_once()
    _, kwargs = mock_upload.call_args
    assert kwargs["filename"] == "teams"
    assert all(team["league"] == "WNBA" for team in kwargs["data"])


@patch.object(WNBAApi, "load_to_bq")
@patch.object(WNBAApi, "upload")
@patch.object(WNBAApi, "get_teams")
def test_ingest_teams_tags_every_record_with_wnba_league(
    mock_get_teams, mock_upload, mock_load_to_bq
):
    mock_get_teams.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]
    client = WNBAApi(bucket="hoop-brain-raw-data")

    client.ingest_teams()

    _, kwargs = mock_upload.call_args
    leagues = [team["league"] for team in kwargs["data"]]
    assert leagues == ["WNBA", "WNBA", "WNBA"]
