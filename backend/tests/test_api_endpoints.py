import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_get_challenge_details():
    response = client.get("/challenge/authentication-debug/details")
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "authentication-debug"
    assert "title" in data

def test_leaderboard_endpoint():
    response = client.get("/api/leaderboard")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_leaderboard_stats_endpoint():
    response = client.get("/api/leaderboard/stats")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_session_start_endpoint():
    resp = client.get("/challenge/authentication-debug/details")
    challenge_id = resp.json()["id"]

    response = client.post("/api/sessions/start", json={
        "challenge_id": challenge_id,
        "name": "Test User"
    })
    assert response.status_code == 201
    data = response.json()
    assert "session_id" in data
    assert "starter_code" in data
