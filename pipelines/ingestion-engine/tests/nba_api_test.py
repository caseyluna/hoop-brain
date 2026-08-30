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


@patch.object(NBAApi, "load_to_bq")
@patch.object(NBAApi, "upload")
@patch.object(NBAApi, "get_player_bio_stats")
@patch.object(NBAApi, "get_players")
def test_ingest_players_uploads_then_loads(
    mock_get_players, mock_get_bio_stats, mock_upload, mock_load_to_bq
):
    mock_get_players.return_value = [
        {"id": 1, "full_name": "Player A", "is_active": True},
        {"id": 2, "full_name": "Player B", "is_active": False},
    ]
    mock_get_bio_stats.return_value = []
    client = NBAApi(bucket="hoop-brain-raw-data")

    client.ingest_players()

    mock_load_to_bq.assert_called_once_with(filename="players")
    mock_upload.assert_called_once()
    _, kwargs = mock_upload.call_args
    assert kwargs["filename"] == "players"
    assert all(player["league"] == "NBA" for player in kwargs["data"])


@patch.object(NBAApi, "load_to_bq")
@patch.object(NBAApi, "upload")
@patch.object(NBAApi, "get_player_bio_stats")
@patch.object(NBAApi, "get_players")
def test_ingest_players_merges_bio_stats_by_player_id(
    mock_get_players, mock_get_bio_stats, mock_upload, mock_load_to_bq
):
    mock_get_players.return_value = [
        {"id": 1, "full_name": "Active Player", "is_active": True},
        {"id": 2, "full_name": "Retired Player", "is_active": False},
    ]
    mock_get_bio_stats.return_value = [
        {
            "PLAYER_ID": 1,
            "TEAM_ID": 100,
            "TEAM_ABBREVIATION": "LAL",
            "AGE": 25.0,
            "PLAYER_HEIGHT": "6-9",
            "PLAYER_HEIGHT_INCHES": 81,
            "PLAYER_WEIGHT": "220",
            "COLLEGE": "Duke",
            "COUNTRY": "USA",
            "DRAFT_YEAR": "2020",
            "DRAFT_ROUND": "1",
            "DRAFT_NUMBER": "5",
        }
    ]
    client = NBAApi(bucket="hoop-brain-raw-data")

    client.ingest_players()

    _, kwargs = mock_upload.call_args
    players_by_id = {player["id"]: player for player in kwargs["data"]}

    active_player = players_by_id[1]
    assert active_player["team_abbreviation"] == "LAL"
    assert active_player["age"] == 25.0
    assert active_player["height"] == "6-9"
    assert active_player["college"] == "Duke"

    retired_player = players_by_id[2]
    assert retired_player["team_abbreviation"] is None
    assert retired_player["age"] is None
    assert retired_player["height"] is None


@patch.object(NBAApi, "load_to_bq")
@patch.object(NBAApi, "upload")
@patch.object(NBAApi, "get_player_bio_stats")
def test_ingest_players_passes_season_through_to_bio_stats(
    mock_get_bio_stats, mock_upload, mock_load_to_bq
):
    mock_get_bio_stats.return_value = []
    client = NBAApi(bucket="hoop-brain-raw-data")

    with patch.object(NBAApi, "get_players", return_value=[]):
        client.ingest_players(season="2024-25")

    mock_get_bio_stats.assert_called_once_with(season="2024-25")


@patch.object(NBAApi, "load_to_bq")
@patch.object(NBAApi, "upload")
@patch.object(NBAApi, "get_player_bio_stats")
@patch.object(NBAApi, "get_players")
def test_ingest_players_degrades_gracefully_when_bio_stats_call_fails(
    mock_get_players, mock_get_bio_stats, mock_upload, mock_load_to_bq
):
    mock_get_players.return_value = [{"id": 1, "full_name": "Player A"}]
    mock_get_bio_stats.side_effect = TimeoutError("stats.nba.com timed out")
    client = NBAApi(bucket="hoop-brain-raw-data")

    client.ingest_players()

    mock_upload.assert_called_once()
    mock_load_to_bq.assert_called_once_with(filename="players")
    _, kwargs = mock_upload.call_args
    player = kwargs["data"][0]
    assert player["league"] == "NBA"
    assert player["team_id"] is None
    assert player["age"] is None
