import pytest
from fastapi.testclient import TestClient

from main import app
from database.connection import SessionLocal
from models.challenge import Challenge
from config import ADMIN_KEY

client = TestClient(app)

ADMIN_HEADERS = {"X-Admin-Key": ADMIN_KEY} if ADMIN_KEY else {}


def setup_module():
    db = SessionLocal()
    from sqlalchemy import text

    slugs = ["test-default-indiv", "test-team-challenge", "test-team-hp-slug", "test-team-rej-slug", "test-team-ws-slug"]
    for slug in slugs:
        ch = db.query(Challenge).filter(Challenge.slug == slug).first()
        if ch:
            cid = ch.id
            db.execute(text("DELETE FROM evaluations WHERE submission_id IN (SELECT id FROM submissions WHERE challenge_id = :cid)"), {"cid": cid})
            db.execute(text("DELETE FROM submissions WHERE challenge_id = :cid"), {"cid": cid})
            db.execute(text("DELETE FROM chat_messages WHERE session_id IN (SELECT id FROM challenge_sessions WHERE challenge_id = :cid)"), {"cid": cid})
            db.execute(text("DELETE FROM challenge_sessions WHERE challenge_id = :cid"), {"cid": cid})
            db.execute(text("DELETE FROM team_members WHERE team_id IN (SELECT id FROM teams WHERE challenge_id = :cid)"), {"cid": cid})
            db.execute(text("DELETE FROM teams WHERE challenge_id = :cid"), {"cid": cid})
            db.execute(text("DELETE FROM challenges WHERE id = :cid"), {"cid": cid})
            db.commit()
    db.close()


def test_create_individual_challenge_defaults():
    payload = {
        "title": "Default Individual Challenge",
        "slug": "test-default-indiv",
        "category": "Testing",
        "difficulty": "Easy",
        "time_limit": 30,
        "description": "Test desc",
        "scenario": "Test scenario",
        "rules": "Test rules",
        "starter_code": "# code",
        "official_solution": "# solution"
    }
    response = client.post("/api/admin/challenges", json=payload, headers=ADMIN_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["mode"] == "individual"
    assert data["team_size"] == 1


def test_create_team_challenge_invalid_size_rejected():
    payload = {
        "title": "Invalid Team Challenge",
        "slug": "test-team-invalid",
        "category": "Testing",
        "difficulty": "Easy",
        "time_limit": 30,
        "description": "Test desc",
        "scenario": "Test scenario",
        "rules": "Test rules",
        "starter_code": "# code",
        "official_solution": "# solution",
        "mode": "team",
        "team_size": 1
    }
    response = client.post("/api/admin/challenges", json=payload, headers=ADMIN_HEADERS)
    assert response.status_code == 422  # Pydantic validation error for team_size < 2


def test_create_and_update_team_challenge_validation():
    # 1. Create valid team challenge
    payload = {
        "title": "Valid Team Challenge",
        "slug": "test-team-challenge",
        "category": "Testing",
        "difficulty": "Hard",
        "time_limit": 60,
        "description": "Test desc",
        "scenario": "Test scenario",
        "rules": "Test rules",
        "starter_code": "# code",
        "official_solution": "# solution",
        "mode": "team",
        "team_size": 4
    }
    create_res = client.post("/api/admin/challenges", json=payload, headers=ADMIN_HEADERS)
    assert create_res.status_code == 201
    challenge_id = create_res.json()["id"]
    assert create_res.json()["mode"] == "team"
    assert create_res.json()["team_size"] == 4

    # 2. Update to mode="individual" without setting team_size=1 -> Rejected
    update_res = client.put(
        f"/api/admin/challenges/{challenge_id}",
        json={"mode": "individual"},
        headers=ADMIN_HEADERS
    )
    assert update_res.status_code in (400, 422)

    # 3. Update to mode="individual" AND team_size=1 -> Allowed
    valid_update_res = client.put(
        f"/api/admin/challenges/{challenge_id}",
        json={"mode": "individual", "team_size": 1},
        headers=ADMIN_HEADERS
    )
    assert valid_update_res.status_code == 200
    assert valid_update_res.json()["mode"] == "individual"
    assert valid_update_res.json()["team_size"] == 1


def test_get_challenges_public_api_includes_team_fields():
    # GET /challenges
    res_list = client.get("/challenges")
    assert res_list.status_code == 200
    items = res_list.json()
    assert len(items) > 0
    first_item = items[0]
    assert "id" in first_item
    assert "mode" in first_item
    assert "team_size" in first_item

    # GET /challenge/{slug}
    res_single = client.get("/challenge/test-default-indiv")
    assert res_single.status_code == 200
    single_data = res_single.json()
    assert single_data["mode"] == "individual"
    assert single_data["team_size"] == 1


def test_create_team_on_individual_challenge_rejected():
    db = SessionLocal()
    from models.user import User
    u = db.query(User).filter(User.email == "team_user1@1code.com").first()
    if not u:
        u = User(name="Team User 1", email="team_user1@1code.com", password_hash="hash")
        db.add(u)
        db.commit()

    indiv_ch = db.query(Challenge).filter(Challenge.slug == "test-default-indiv").first()
    u_id = u.id
    ch_id = indiv_ch.id
    db.close()

    res = client.post("/api/teams", json={
        "challenge_id": ch_id,
        "user_id": u_id,
        "team_name": "Invalid Individual Team"
    })
    assert res.status_code == 400
    assert "not configured for team mode" in res.json()["detail"]


def test_team_full_happy_path():
    db = SessionLocal()
    from models.user import User
    from models.submission import Submission
    from models.evaluation import Evaluation
    from models.team import Team

    # Create 4 test users
    user_ids = []
    for i in range(1, 5):
        email = f"user_{i}_hp@1code.com"
        u = db.query(User).filter(User.email == email).first()
        if not u:
            u = User(name=f"User {i}", email=email, password_hash="hash")
            db.add(u)
            db.commit()
            db.refresh(u)
        user_ids.append(u.id)

    # Create a team challenge
    ch = db.query(Challenge).filter(Challenge.slug == "test-team-hp-slug").first()
    if not ch:
        ch = Challenge(
            slug="test-team-hp-slug",
            title="Team Happy Path Challenge",
            description="Desc",
            scenario="Scenario",
            rules="Rules",
            time_limit=45,
            category="Testing",
            starter_code="def solution(): pass",
            official_solution="def solution(): return True",
            mode="team",
            team_size=4,
            is_active=True
        )
        db.add(ch)
        db.commit()
        db.refresh(ch)
    ch_id = ch.id
    ch_slug = ch.slug
    db.close()

    # 1. User 1 creates team
    create_res = client.post("/api/teams", json={
        "challenge_id": ch_id,
        "user_id": user_ids[0],
        "team_name": "Alpha Team"
    })
    assert create_res.status_code == 201
    team_data = create_res.json()
    team_id = team_data["id"]
    invite_code = team_data["invite_code"]
    assert team_data["status"] == "forming"
    assert len(team_data["members"]) == 1

    # 2. Leader attempts start with < 2 members -> REJECTED
    start_fail = client.post(f"/api/teams/{team_id}/start", json={"user_id": user_ids[0]})
    assert start_fail.status_code == 400
    assert "Need at least 2 members to start" in start_fail.json()["detail"]

    # 3. User 2 joins via browse list
    open_teams_res = client.get(f"/api/challenge/{ch_slug}/teams")
    assert open_teams_res.status_code == 200
    assert len(open_teams_res.json()) >= 1

    open_teams_for_creator = client.get(f"/api/challenge/{ch_slug}/teams?user_id={user_ids[0]}")
    assert open_teams_for_creator.status_code == 200
    assert all(team["id"] != team_id for team in open_teams_for_creator.json())

    open_teams_for_user2 = client.get(f"/api/challenge/{ch_slug}/teams?user_id={user_ids[1]}")
    assert open_teams_for_user2.status_code == 200
    assert any(team["id"] == team_id for team in open_teams_for_user2.json())

    join2_res = client.post("/api/teams/join", json={
        "user_id": user_ids[1],
        "team_id": team_id
    })
    assert join2_res.status_code == 200
    assert len(join2_res.json()["members"]) == 2

    # 4. User 3 joins via invite_code
    join3_res = client.post("/api/teams/join", json={
        "user_id": user_ids[2],
        "invite_code": invite_code
    })
    assert join3_res.status_code == 200
    assert len(join3_res.json()["members"]) == 3

    # 5. Leader starts team session -> SUCCESS
    start_res = client.post(f"/api/teams/{team_id}/start", json={"user_id": user_ids[0]})
    assert start_res.status_code == 200
    session_data = start_res.json()
    session_id = session_data["session_id"]
    assert session_data["starter_code"] == "def solution(): pass"

    # 6. Team members chat and save code
    chat_res = client.post(f"/api/sessions/{session_id}/chat", json={
        "message": "Hello team, let's fix this bug",
        "actor_user_id": user_ids[1]
    })
    assert chat_res.status_code == 200
    assert "reply" in chat_res.json()

    save_res = client.post(f"/api/sessions/{session_id}/save-code", json={
        "code": "def solution(): return True",
        "actor_user_id": user_ids[2]
    })
    assert save_res.status_code == 200
    assert save_res.json()["saved"] is True

    # 7. Non-member chat attempt -> REJECTED
    bad_actor_chat = client.post(f"/api/sessions/{session_id}/chat", json={
        "message": "Imposter message",
        "actor_user_id": user_ids[3]
    })
    assert bad_actor_chat.status_code == 403

    # 8. Submit session
    sub_res = client.post(f"/api/sessions/{session_id}/submit", json={
        "actor_user_id": user_ids[0]
    })
    assert sub_res.status_code == 200
    submission_id = sub_res.json()["submission_id"]

    # 9. Verify Submission DB record
    db = SessionLocal()
    sub_record = db.query(Submission).filter(Submission.id == submission_id).first()
    assert sub_record is not None
    assert sub_record.team_id == team_id
    assert sub_record.user_id is None
    assert sub_record.name == "Alpha Team"

    team_record = db.query(Team).filter(Team.id == team_id).first()
    assert team_record.status == "submitted"

    eval_record = db.query(Evaluation).filter(Evaluation.submission_id == submission_id).first()
    assert eval_record is not None
    db.close()


def test_team_join_rejections():
    db = SessionLocal()
    from models.user import User
    from models.team import Team

    u_leader = db.query(User).filter(User.email == "leader_rej@1code.com").first()
    if not u_leader:
        u_leader = User(name="Leader User", email="leader_rej@1code.com", password_hash="hash")
        db.add(u_leader)
        db.commit()

    u_m2 = db.query(User).filter(User.email == "m2_rej@1code.com").first()
    if not u_m2:
        u_m2 = User(name="Member 2", email="m2_rej@1code.com", password_hash="hash")
        db.add(u_m2)
        db.commit()

    u_m3 = db.query(User).filter(User.email == "m3_rej@1code.com").first()
    if not u_m3:
        u_m3 = User(name="Member 3", email="m3_rej@1code.com", password_hash="hash")
        db.add(u_m3)
        db.commit()

    leader_id = u_leader.id
    m2_id = u_m2.id
    m3_id = u_m3.id

    ch = db.query(Challenge).filter(Challenge.slug == "test-team-rej-slug").first()
    if not ch:
        ch = Challenge(
            slug="test-team-rej-slug",
            title="Rejection Challenge",
            description="Desc",
            scenario="Scenario",
            rules="Rules",
            time_limit=45,
            category="Testing",
            starter_code="def pass(): pass",
            official_solution="def pass(): pass",
            mode="team",
            team_size=2,
            is_active=True
        )
        db.add(ch)
        db.commit()
        db.refresh(ch)
    ch_id = ch.id
    db.close()

    # Create team (size cap 2)
    create_res = client.post("/api/teams", json={
        "challenge_id": ch_id,
        "user_id": leader_id,
        "team_name": "Small Team"
    })
    team_id = create_res.json()["id"]

    # 1. Invalid invite code -> 404
    bad_code = client.post("/api/teams/join", json={"user_id": m2_id, "invite_code": "NONEXISTENT"})
    assert bad_code.status_code == 404

    # 2. Join succeeds for u_m2
    j2 = client.post("/api/teams/join", json={"user_id": m2_id, "team_id": team_id})
    assert j2.status_code == 200

    # 3. Join attempt when team is full (size 2) -> 400
    j3 = client.post("/api/teams/join", json={"user_id": m3_id, "team_id": team_id})
    assert j3.status_code == 400
    assert "Team is full" in j3.json()["detail"]

    # 4. Join attempt on started team -> 400
    start_res = client.post(f"/api/teams/{team_id}/start", json={"user_id": leader_id})
    assert start_res.status_code == 200

    j_started = client.post("/api/teams/join", json={"user_id": m3_id, "team_id": team_id})
    assert j_started.status_code == 400
    assert "Team has already started or finished" in j_started.json()["detail"]


def test_team_websocket_connection():
    db = SessionLocal()
    from models.user import User

    u1 = db.query(User).filter(User.email == "ws_user1@1code.com").first()
    if not u1:
        u1 = User(name="WS User 1", email="ws_user1@1code.com", password_hash="hash")
        db.add(u1)
        db.commit()

    u2 = db.query(User).filter(User.email == "ws_user2@1code.com").first()
    if not u2:
        u2 = User(name="WS User 2", email="ws_user2@1code.com", password_hash="hash")
        db.add(u2)
        db.commit()

    u_outsider = db.query(User).filter(User.email == "ws_outsider@1code.com").first()
    if not u_outsider:
        u_outsider = User(name="Outsider", email="ws_outsider@1code.com", password_hash="hash")
        db.add(u_outsider)
        db.commit()

    u1_id = u1.id
    u2_id = u2.id
    outsider_id = u_outsider.id

    ch = db.query(Challenge).filter(Challenge.slug == "test-team-ws-slug").first()
    if not ch:
        ch = Challenge(
            slug="test-team-ws-slug",
            title="WS Challenge",
            description="Desc",
            scenario="Scenario",
            rules="Rules",
            time_limit=45,
            category="Testing",
            starter_code="def pass(): pass",
            official_solution="def pass(): pass",
            mode="team",
            team_size=4,
            is_active=True
        )
        db.add(ch)
        db.commit()
        db.refresh(ch)
    ch_id = ch.id
    db.close()

    create_res = client.post("/api/teams", json={
        "challenge_id": ch_id,
        "user_id": u1_id,
        "team_name": "WS Team"
    })
    team_id = create_res.json()["team_id"]
    client.post("/api/teams/join", json={"user_id": u2_id, "team_id": team_id})

    # 1. Non-member connection rejected
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/teams/{team_id}/ws?user_id={outsider_id}"):
            pass

    # 2. Member connection & broadcast check
    with client.websocket_connect(f"/api/teams/{team_id}/ws?user_id={u1_id}") as ws1:
        with client.websocket_connect(f"/api/teams/{team_id}/ws?user_id={u2_id}") as ws2:
            # ws1 should receive member_online for u2
            msg = ws1.receive_json()
            assert msg["type"] == "member_online"
            assert msg["user_id"] == u2_id

            # Test code_sync broadcast from ws2
            ws2.send_json({"type": "code_sync", "code": "def solution(): return 42"})
            code_msg = ws1.receive_json()
            assert code_msg["type"] == "code_sync"
            assert code_msg["code"] == "def solution(): return 42"

            # Test mute_state broadcast from ws1
            ws1.send_json({"type": "mute_state", "is_muted": False})
            mute_msg = ws2.receive_json()
            assert mute_msg["type"] == "mute_state"
            assert mute_msg["is_muted"] is False

