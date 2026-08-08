import pytest
from fastapi.testclient import TestClient

from main import app
from database.connection import SessionLocal
from models.challenge import Challenge
from models.user import User
from models.submission import Submission
from config import ADMIN_KEY

client = TestClient(app)
ADMIN_HEADERS = {"X-Admin-Key": ADMIN_KEY} if ADMIN_KEY else {}


def setup_module():
    db = SessionLocal()
    from sqlalchemy import text

    slugs = ["test-hard-del-slug", "test-soft-del-slug"]
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

    test_emails = ["banned_user_test@1code.com", "admin_user_test@1code.com"]
    for email in test_emails:
        u = db.query(User).filter(User.email == email).first()
        if u:
            uid = u.id
            db.execute(text("DELETE FROM evaluations WHERE submission_id IN (SELECT id FROM submissions WHERE user_id = :uid)"), {"uid": uid})
            db.execute(text("DELETE FROM submissions WHERE user_id = :uid"), {"uid": uid})
            db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": uid})
            db.commit()

    db.close()


def test_challenge_hard_delete_and_soft_delete_archive():
    # 1. Create Challenge A (no submissions) -> Should hard delete
    payload_a = {
        "title": "Hard Delete Challenge",
        "slug": "test-hard-del-slug",
        "category": "Testing",
        "difficulty": "Easy",
        "time_limit": 30,
        "description": "Desc",
        "scenario": "Scenario",
        "rules": "Rules",
        "starter_code": "# code",
        "official_solution": "# solution",
        "mode": "individual",
        "team_size": 1,
    }
    c_res_a = client.post("/api/admin/challenges", json=payload_a, headers=ADMIN_HEADERS)
    assert c_res_a.status_code == 201
    cid_a = c_res_a.json()["id"]

    del_res_a = client.delete(f"/api/admin/challenges/{cid_a}", headers=ADMIN_HEADERS)
    assert del_res_a.status_code == 200
    del_data_a = del_res_a.json()
    assert del_data_a["deleted"] is True
    assert del_data_a["archived"] is False

    db = SessionLocal()
    assert db.query(Challenge).filter(Challenge.id == cid_a).first() is None
    db.close()

    # 2. Create Challenge B (with submission) -> Should soft delete (archive)
    payload_b = {
        "title": "Soft Delete Challenge",
        "slug": "test-soft-del-slug",
        "category": "Testing",
        "difficulty": "Medium",
        "time_limit": 30,
        "description": "Desc",
        "scenario": "Scenario",
        "rules": "Rules",
        "starter_code": "# code",
        "official_solution": "# solution",
        "mode": "individual",
        "team_size": 1,
    }
    c_res_b = client.post("/api/admin/challenges", json=payload_b, headers=ADMIN_HEADERS)
    assert c_res_b.status_code == 201
    cid_b = c_res_b.json()["id"]

    db = SessionLocal()
    dummy_user = db.query(User).first()
    dummy_user_id = dummy_user.id if dummy_user else 1

    dummy_sub = Submission(
        name="Tester",
        user_id=dummy_user_id,
        team_id=None,
        challenge_id=cid_b,
        late=False,
        overall_score=85,
        feedback="Good job",
    )
    db.add(dummy_sub)
    db.commit()
    db.close()

    del_res_b = client.delete(f"/api/admin/challenges/{cid_b}", headers=ADMIN_HEADERS)
    assert del_res_b.status_code == 200
    del_data_b = del_res_b.json()
    assert del_data_b["deleted"] is False
    assert del_data_b["archived"] is True

    # Default list excludes archived challenge
    list_res_default = client.get("/api/admin/challenges", headers=ADMIN_HEADERS)
    assert list_res_default.status_code == 200
    slugs_default = [c["slug"] for c in list_res_default.json()]
    assert "test-soft-del-slug" not in slugs_default

    # List with include_archived=true includes it
    list_res_archived = client.get("/api/admin/challenges?include_archived=true", headers=ADMIN_HEADERS)
    assert list_res_archived.status_code == 200
    slugs_archived = [c["slug"] for c in list_res_archived.json()]
    assert "test-soft-del-slug" in slugs_archived


def test_user_ban_unban_and_login_blocking():
    # 1. Register test user
    reg_res = client.post("/api/register", json={
        "name": "Banned Test User",
        "email": "banned_user_test@1code.com",
        "password": "userpass123",
    })
    assert reg_res.status_code == 200 or reg_res.status_code == 201
    user_id = reg_res.json()["user_id"] if "user_id" in reg_res.json() else reg_res.json()["id"]

    # 2. Ban user via Admin API
    ban_res = client.post(f"/api/admin/users/{user_id}/ban", json={"reason": "Terms Violation Test"}, headers=ADMIN_HEADERS)
    assert ban_res.status_code == 200
    assert ban_res.json()["is_banned"] is True
    assert ban_res.json()["banned_reason"] == "Terms Violation Test"

    # 3. Login attempt by banned user -> 403 Forbidden
    login_res = client.post("/api/login", json={
        "email": "banned_user_test@1code.com",
        "password": "userpass123",
    })
    assert login_res.status_code == 403
    assert "This account has been suspended" in login_res.json()["detail"]

    # 4. Unban user via Admin API
    unban_res = client.post(f"/api/admin/users/{user_id}/unban", headers=ADMIN_HEADERS)
    assert unban_res.status_code == 200
    assert unban_res.json()["is_banned"] is False

    # 5. Login attempt by unbanned user -> 200 OK
    login_res_2 = client.post("/api/login", json={
        "email": "banned_user_test@1code.com",
        "password": "userpass123",
    })
    assert login_res_2.status_code == 200
    assert login_res_2.json()["user_id"] == user_id


def test_admin_user_cannot_be_banned():
    db = SessionLocal()
    admin = db.query(User).filter(User.email == "admin_user_test@1code.com").first()
    if not admin:
        from routes.auth import hash_password
        admin = User(name="Admin User Test", email="admin_user_test@1code.com", password_hash=hash_password("admin123"), is_admin=True)
        db.add(admin)
        db.commit()
        db.refresh(admin)
    admin_id = admin.id
    db.close()

    ban_res = client.post(f"/api/admin/users/{admin_id}/ban", json={"reason": "Attempt ban"}, headers=ADMIN_HEADERS)
    assert ban_res.status_code == 400
    assert "Admin users cannot be banned" in ban_res.json()["detail"]
