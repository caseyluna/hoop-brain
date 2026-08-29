# api/tests/test_teams.py


def test_read_teams(client):
    response = client.get("/api/v1/teams/")
    assert response.status_code == 200
    teams = response.json()
    assert all(team["league"] in ("NBA", "WNBA") for team in teams)
