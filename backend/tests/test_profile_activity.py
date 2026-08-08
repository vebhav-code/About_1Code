from datetime import date, timedelta
from fastapi.testclient import TestClient

from main import app
from database.connection import SessionLocal
from models.user import User
from models.user_activity import UserActivity
from services.activity_service import record_visit

client = TestClient(app)


def test_login_records_visit_idempotent():
    db = SessionLocal()
    email = "streak-idempotent@1code.com"
    user = db.query(User).filter(User.email == email).first()
    if not user:
        from routes.auth import hash_password
        user = User(name="Streak User", email=email, password_hash=hash_password("password123"))
        db.add(user)
        db.commit()
        db.refresh(user)
    db.query(UserActivity).filter(UserActivity.user_id == user.id).delete()
    user.current_streak = 0
    user.longest_streak = 0
    db.commit()
    user_id = user.id
    db.close()

    # Login twice on the same day
    res1 = client.post("/api/login", json={"email": email, "password": "password123"})
    assert res1.status_code == 200

    res2 = client.post("/api/login", json={"email": email, "password": "password123"})
    assert res2.status_code == 200

    db = SessionLocal()
    today = date.today()
    visits = (
        db.query(UserActivity)
        .filter(UserActivity.user_id == user_id, UserActivity.visit_date == today)
        .all()
    )
    assert len(visits) == 1

    profile_res = client.get(f"/api/users/{user_id}/profile")
    assert profile_res.status_code == 200
    data = profile_res.json()
    assert data["current_streak"] == 1
    assert data["longest_streak"] >= 1
    assert data["last_active_date"] == today.isoformat()
    assert len(data["visit_calendar"]) == 90
    db.close()


def test_consecutive_days_streak_and_gap_reset():
    db = SessionLocal()
    email = "streak-consecutive@1code.com"
    user = db.query(User).filter(User.email == email).first()
    if not user:
        from routes.auth import hash_password
        user = User(name="Streak Multi User", email=email, password_hash=hash_password("password123"))
        db.add(user)
        db.commit()
        db.refresh(user)

    # Clean previous activity rows for isolation
    db.query(UserActivity).filter(UserActivity.user_id == user.id).delete()
    user.current_streak = 0
    user.longest_streak = 0
    db.commit()

    today = date.today()
    d1 = today - timedelta(days=2)
    d2 = today - timedelta(days=1)

    # Insert visits for d1 and d2
    for d in [d1, d2]:
        existing = db.query(UserActivity).filter(UserActivity.user_id == user.id, UserActivity.visit_date == d).first()
        if not existing:
            db.add(UserActivity(user_id=user.id, visit_date=d))
    db.commit()

    record_visit(db, user.id)

    db.refresh(user)
    assert user.current_streak == 3
    assert user.longest_streak >= 3

    # Now test gap reset: clear activity and insert visit 5 days ago and today only
    db.query(UserActivity).filter(UserActivity.user_id == user.id).delete()
    db.commit()

    d_old1 = today - timedelta(days=6)
    d_old2 = today - timedelta(days=5)
    d_old3 = today - timedelta(days=4)
    d_old4 = today - timedelta(days=3)
    for d in [d_old1, d_old2, d_old3, d_old4]:
        db.add(UserActivity(user_id=user.id, visit_date=d))
    db.commit()

    record_visit(db, user.id)
    db.refresh(user)

    # Today is visited, but yesterday is missing -> current_streak = 1, longest_streak = 4
    assert user.current_streak == 1
    assert user.longest_streak == 4
    db.close()


def test_patch_profile_updates_bio_and_avatar():
    db = SessionLocal()
    email = "patch-profile@1code.com"
    user = db.query(User).filter(User.email == email).first()
    if not user:
        from routes.auth import hash_password
        user = User(name="Patch User", email=email, password_hash=hash_password("password123"))
        db.add(user)
        db.commit()
        db.refresh(user)
    user_id = user.id
    db.close()

    patch_res = client.patch(
        f"/api/users/{user_id}/profile",
        json={"bio": "Full-stack developer building 1Code.", "avatar_url": "https://example.com/avatar.png"},
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["bio"] == "Full-stack developer building 1Code."
    assert data["avatar_url"] == "https://example.com/avatar.png"

    get_res = client.get(f"/api/users/{user_id}/profile")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["bio"] == "Full-stack developer building 1Code."
    assert get_data["avatar_url"] == "https://example.com/avatar.png"


def test_patch_profile_validates_bio_length():
    db = SessionLocal()
    user = db.query(User).first()
    db.close()
    if not user:
        return

    long_bio = "A" * 300
    res = client.patch(f"/api/users/{user.id}/profile", json={"bio": long_bio})
    assert res.status_code == 422


def test_difficulty_breakdown_response():
    db = SessionLocal()
    user = db.query(User).first()
    db.close()
    if not user:
        return

    res = client.get(f"/api/users/{user.id}/profile")
    assert res.status_code == 200
    data = res.json()
    assert "difficulty_breakdown" in data
    diff = data["difficulty_breakdown"]
    assert "Easy" in diff and "solved" in diff["Easy"] and "total" in diff["Easy"]
    assert "Medium" in diff and "solved" in diff["Medium"] and "total" in diff["Medium"]
    assert "Hard" in diff and "solved" in diff["Hard"] and "total" in diff["Hard"]

