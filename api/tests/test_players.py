# api/tests/test_players.py


def test_read_players(client):
    response = client.get("/api/v1/players/")
    assert response.status_code == 200
    players = response.json()
    assert all(player["league"] in ("NBA", "WNBA") for player in players)


def test_read_players_filtered_by_nba(client):
    response = client.get("/api/v1/players/?league=NBA")
    assert response.status_code == 200
    players = response.json()
    assert all(player["league"] == "NBA" for player in players)


def test_read_players_filtered_by_wnba(client):
    response = client.get("/api/v1/players/?league=WNBA")
    assert response.status_code == 200
    players = response.json()
    assert all(player["league"] == "WNBA" for player in players)


def test_read_players_invalid_league(client):
    response = client.get("/api/v1/players/?league=XYZ")
    assert response.status_code == 422


def test_read_players_search(client):
    response = client.get("/api/v1/players/?search=LeBron")
    assert response.status_code == 200
    players = response.json()
    assert len(players) >= 1
    assert all("lebron" in player["full_name"].lower() for player in players)


def test_read_players_pagination(client):
    response = client.get("/api/v1/players/?limit=5&offset=0")
    assert response.status_code == 200
    assert len(response.json()) <= 5


def test_read_player_detail(client):
    listed = client.get("/api/v1/players/?limit=1").json()
    assert len(listed) == 1
    player_id = listed[0]["id"]

    response = client.get(f"/api/v1/players/{player_id}")
    assert response.status_code == 200
    assert response.json()["id"] == player_id


def test_read_player_detail_not_found(client):
    response = client.get("/api/v1/players/999999999")
    assert response.status_code == 404
