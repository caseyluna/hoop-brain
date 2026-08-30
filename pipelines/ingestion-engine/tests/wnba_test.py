from unittest.mock import Mock, patch

from modules.wnba import WNBAApi, _int, _na


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


def test_na_normalizes_r_na_string_and_blanks_to_none():
    assert _na("NA") is None
    assert _na("") is None
    assert _na("  ") is None
    assert _na(None) is None
    assert _na(" Connecticut ") == "Connecticut"
    assert _na(180) == 180


def test_int_coerces_present_values_and_normalizes_missing():
    assert _int("1611661320") == 1611661320
    assert _int("NA") is None
    assert _int("") is None
    assert _int(None) is None
    assert _int(180) == 180


def test_get_players_parses_wehoop_playerindex_csv(tmp_path):
    # Mirrors a real `wehoop::wnba_playerindex()` pull (CAL-159, verified against real
    # infra): R's readr::write_csv encodes missing values as the literal string "NA" --
    # exercised here via TEAM_ID/DRAFT_ROUND/DRAFT_NUMBER/COUNTRY on the retired player row.
    csv_path = tmp_path / "wnba_players__PlayerIndex.csv"
    csv_path.write_text(
        "PERSON_ID,PLAYER_LAST_NAME,PLAYER_FIRST_NAME,PLAYER_SLUG,TEAM_ID,TEAM_SLUG,"
        "TEAM_CITY,TEAM_NAME,TEAM_ABBREVIATION,JERSEY_NUMBER,POSITION,HEIGHT,WEIGHT,"
        "COLLEGE,COUNTRY,DRAFT_YEAR,DRAFT_ROUND,DRAFT_NUMBER,ROSTER_STATUS,PTS,REB,AST,"
        "STATS_TIMEFRAME,FROM_YEAR,TO_YEAR,SUPPLEMENTAL_STATUS\n"
        "203399,Wilson,A'ja,aja-wilson,1611661319,aces,Las Vegas,Aces,LVA,22,C,6-4,195,"
        "South Carolina,USA,2018,1,1,1,22.8,9.4,2.3,Career,2018,2026,0\n"
        "100001,Retired,Player,retired-player,NA,NA,NA,NA,NA,NA,NA,6-0,NA,NA,NA,2001,NA,"
        "NA,NA,5.0,2.0,1.0,Career,2001,2005,0\n"
    )

    players = WNBAApi.get_players(csv_path=csv_path)

    assert players[0] == {
        "id": 203399,
        "first_name": "A'ja",
        "last_name": "Wilson",
        "full_name": "A'ja Wilson",
        "team_id": 1611661319,
        "team_city": "Las Vegas",
        "team_name": "Aces",
        "team_abbreviation": "LVA",
        "jersey_number": "22",
        "position": "C",
        "height": "6-4",
        "weight": 195,
        "college": "South Carolina",
        "country": "USA",
        "draft_year": 2018,
        "draft_round": 1,
        "draft_number": 1,
        "roster_status": "1",
        "from_year": 2018,
        "to_year": 2026,
    }
    # the "NA" sentinel R writes for missing cells is normalized to None, not left as
    # the literal string "NA" -- team fields, draft fields, and country all exercise this.
    retired = players[1]
    assert retired["team_id"] is None
    assert retired["team_city"] is None
    assert retired["country"] is None
    assert retired["draft_round"] is None
    assert retired["draft_number"] is None


@patch.object(WNBAApi, "load_to_bq")
@patch.object(WNBAApi, "upload")
@patch.object(WNBAApi, "get_players")
def test_ingest_players_tags_every_record_with_wnba_league(
    mock_get_players, mock_upload, mock_load_to_bq
):
    mock_get_players.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]
    client = WNBAApi(bucket="hoop-brain-raw-data")

    client.ingest_players(csv_path="unused.csv")

    mock_load_to_bq.assert_called_once_with(filename="players")
    _, kwargs = mock_upload.call_args
    assert kwargs["filename"] == "players"
    leagues = [player["league"] for player in kwargs["data"]]
    assert leagues == ["WNBA", "WNBA", "WNBA"]
