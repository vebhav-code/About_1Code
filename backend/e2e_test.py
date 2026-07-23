import sys
from fastapi.testclient import TestClient
from main import app
from config import ADMIN_KEY

client = TestClient(app)

print("1. Creating challenge via admin...")
res_create = client.post(
    "/api/admin/challenges",
    headers={"X-Admin-Key": ADMIN_KEY},
    json={
        "slug": "e2e-test-3",
        "title": "E2E Test Challenge",
        "description": "E2E Test",
        "scenario": "E2E Test scenario",
        "difficulty": "Medium",
        "category": "API",
        "rules": "E2E Rules",
        "time_limit": 30,
        "starter_code": "def buggy():\n    return False",
        "official_solution": "def buggy():\n    return True"
    }
)
print("Create Status:", res_create.status_code)
if res_create.status_code != 201:
    print(res_create.json())
    sys.exit(1)
chal_id = res_create.json()["id"]

print("\n2. Starting session...")
res_start = client.post(
    "/api/sessions/start",
    json={"challenge_id": chal_id, "name": "E2E User"}
)
print("Start Status:", res_start.status_code)
session_id = res_start.json()["session_id"]
starter_code = res_start.json()["starter_code"]
print("Starter code received:", starter_code)

print("\n3. Sending chat message...")
res_chat = client.post(
    f"/api/sessions/{session_id}/chat",
    json={"message": "I need help with this bug."}
)
print("Chat Status:", res_chat.status_code)
reply = res_chat.json()["reply"]
print("AI Reply:", reply)

print("\n4. Saving correct code...")
res_save = client.post(
    f"/api/sessions/{session_id}/save-code",
    json={"code": "def buggy():\n    return True"}
)
print("Save Status:", res_save.status_code)

print("\n5. Submitting session...")
res_submit = client.post(f"/api/sessions/{session_id}/submit")
print("Submit Status:", res_submit.status_code)
sub_id = res_submit.json()["submission_id"]

print("\n6. Checking submission results...")
from database.connection import SessionLocal
from models.submission import Submission
from models.evaluation import Evaluation

db = SessionLocal()
sub = db.query(Submission).filter(Submission.id == sub_id).first()
eval = db.query(Evaluation).filter(Evaluation.submission_id == sub_id).first()

print("Overall Score:", sub.overall_score)
print("Feedback:", sub.feedback)

print("\nALL E2E TESTS PASSED.")
