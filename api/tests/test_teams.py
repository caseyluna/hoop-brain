# api/tests/test_teams.py


def test_read_teams(client):
    response = client.get("/api/v1/teams/")
    assert response.status_code == 200
    teams = response.json()
    assert all(team["league"] in ("NBA", "WNBA") for team in teams)


def test_read_teams_filtered_by_nba(client):
    response = client.get("/api/v1/teams/?league=NBA")
    assert response.status_code == 200
    teams = response.json()
    assert all(team["league"] == "NBA" for team in teams)


def test_read_teams_filtered_by_wnba(client):
    response = client.get("/api/v1/teams/?league=WNBA")
    assert response.status_code == 200
    teams = response.json()
    assert all(team["league"] == "WNBA" for team in teams)


def test_read_teams_invalid_league(client):
    response = client.get("/api/v1/teams/?league=XYZ")
    assert response.status_code == 422
