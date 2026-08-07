import pytest
from fastapi.testclient import TestClient
from main import app
from database.connection import SessionLocal
from models.challenge import Challenge
from models.user import User

client = TestClient(app)


def setup_module():
    db = SessionLocal()
    existing_user = db.query(User).filter(User.email == "test@1code.com").first()
    if not existing_user:
        test_user = User(
            name="Test User",
            email="test@1code.com",
            password_hash="hash",
            is_admin=False
        )
        db.add(test_user)
        db.commit()

    existing = db.query(Challenge).filter(Challenge.slug == "authentication-debug").first()
    if not existing:
        challenge = Challenge(
            slug="authentication-debug",
            title="Authentication Debug",
            description="Fix auth bugs",
            scenario="User login failing",
            difficulty="Medium",
            rules="No cheating",
            time_limit=45,
            category="Authentication",
            starter_code="def login(): pass",
            official_solution="def login(): return True",
            folder_name="authentication-debug",
            is_active=True,
            mode="individual",
            team_size=1,
        )
        db.add(challenge)
        db.commit()
    db.close()


def test_get_challenge_details():
    response = client.get("/challenge/authentication-debug/details")
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "authentication-debug"
    assert "title" in data
    assert "mode" in data
    assert data["mode"] == "individual"
    assert "team_size" in data
    assert data["team_size"] == 1


def test_leaderboard_endpoint():
    response = client.get("/api/leaderboard")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_leaderboard_stats_endpoint():
    response = client.get("/api/leaderboard/stats")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_session_start_endpoint():
    db = SessionLocal()
    user = db.query(User).filter(User.email == "test@1code.com").first()
    challenge = db.query(Challenge).filter(Challenge.slug == "authentication-debug").first()
    db.close()

    response = client.post("/api/sessions/start", json={
        "challenge_id": challenge.id,
        "user_id": user.id,
        "name": "Test User",
        "hypothesis": "Testing hypothesis"
    })
    assert response.status_code == 201
    data = response.json()
    assert "session_id" in data
    assert "starter_code" in data


def test_session_start_rejects_team_submission_from_team_member():
    db = SessionLocal()
    from models.submission import Submission
    from models.team import Team
    from models.team_member import TeamMember

    user = db.query(User).filter(User.email == "crossmode-user@1code.com").first()
    if not user:
        user = User(name="Crossmode User", email="crossmode-user@1code.com", password_hash="hash")
        db.add(user)
        db.commit()
        db.refresh(user)

    challenge = db.query(Challenge).filter(Challenge.slug == "crossmode-check").first()
    if not challenge:
        challenge = Challenge(
            slug="crossmode-check",
            title="Crossmode Challenge",
            description="Desc",
            scenario="Scenario",
            rules="Rules",
            time_limit=30,
            category="Testing",
            starter_code="def solution(): pass",
            official_solution="def solution(): return True",
            mode="individual",
            team_size=1,
            is_active=True,
        )
        db.add(challenge)
        db.commit()
        db.refresh(challenge)

    team = db.query(Team).filter(Team.challenge_id == challenge.id).first()
    if not team:
        team = Team(
            challenge_id=challenge.id,
            name="Crossmode Team",
            invite_code="CROSS01",
            leader_user_id=user.id,
            status="forming",
        )
        db.add(team)
        db.commit()
        db.refresh(team)

    member = db.query(TeamMember).filter(TeamMember.team_id == team.id, TeamMember.user_id == user.id).first()
    if not member:
        db.add(TeamMember(team_id=team.id, user_id=user.id))
        db.commit()

    existing = db.query(Submission).filter(Submission.challenge_id == challenge.id, Submission.team_id == team.id).first()
    if not existing:
        db.add(Submission(name="Team submission", user_id=None, team_id=team.id, challenge_id=challenge.id, feedback="", overall_score=0))
        db.commit()
    user_id = user.id
    challenge_id = challenge.id
    db.close()

    response = client.post("/api/sessions/start", json={
        "challenge_id": challenge_id,
        "user_id": user_id,
        "name": "Crossmode User",
        "hypothesis": "Testing"
    })
    assert response.status_code == 409
    assert "already submitted" in response.json()["detail"].lower()


def test_team_start_rejects_when_member_already_submitted_individually():
    db = SessionLocal()
    from models.submission import Submission
    from models.team import Team
    from models.team_member import TeamMember

    leader = db.query(User).filter(User.email == "team-start-leader@1code.com").first()
    if not leader:
        leader = User(name="Team Leader", email="team-start-leader@1code.com", password_hash="hash")
        db.add(leader)
        db.commit()
        db.refresh(leader)

    member = db.query(User).filter(User.email == "team-start-member@1code.com").first()
    if not member:
        member = User(name="Team Member", email="team-start-member@1code.com", password_hash="hash")
        db.add(member)
        db.commit()
        db.refresh(member)

    challenge = db.query(Challenge).filter(Challenge.slug == "team-start-member-check").first()
    if not challenge:
        challenge = Challenge(
            slug="team-start-member-check",
            title="Team Start Member Check",
            description="Desc",
            scenario="Scenario",
            rules="Rules",
            time_limit=30,
            category="Testing",
            starter_code="def solution(): pass",
            official_solution="def solution(): return True",
            mode="team",
            team_size=2,
            is_active=True,
        )
        db.add(challenge)
        db.commit()
        db.refresh(challenge)

    team = db.query(Team).filter(Team.challenge_id == challenge.id).first()
    if not team:
        team = Team(
            challenge_id=challenge.id,
            name="Member Check Team",
            invite_code="MEMBER01",
            leader_user_id=leader.id,
            status="forming",
        )
        db.add(team)
        db.commit()
        db.refresh(team)

    existing_member = db.query(TeamMember).filter(TeamMember.team_id == team.id, TeamMember.user_id == leader.id).first()
    if not existing_member:
        db.add(TeamMember(team_id=team.id, user_id=leader.id))
    member_link = db.query(TeamMember).filter(TeamMember.team_id == team.id, TeamMember.user_id == member.id).first()
    if not member_link:
        db.add(TeamMember(team_id=team.id, user_id=member.id))
    db.commit()

    existing_individual = db.query(Submission).filter(Submission.challenge_id == challenge.id, Submission.user_id == member.id).first()
    if not existing_individual:
        db.add(Submission(name="Individual submission", user_id=member.id, team_id=None, challenge_id=challenge.id, feedback="", overall_score=0))
        db.commit()
    team_id = team.id
    leader_id = leader.id
    db.close()

    response = client.post(f"/api/teams/{team_id}/start", json={"user_id": leader_id})
    assert response.status_code == 409
    assert "already submitted" in response.json()["detail"].lower()
