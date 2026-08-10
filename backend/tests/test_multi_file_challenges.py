import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app

from database.connection import SessionLocal
from models.challenge import Challenge
from models.submission import Submission
from models.submission_file import SubmissionFile
from models.user import User
from config import ADMIN_KEY

client = TestClient(app)
ADMIN_HEADERS = {"X-Admin-Key": ADMIN_KEY} if ADMIN_KEY else {}


class MultiFileChallengeTests(unittest.TestCase):

    def setUp(self):
        db = SessionLocal()
        from sqlalchemy import text
        ch = db.query(Challenge).filter(Challenge.slug == "test-mf-standalone-slug").first()
        if ch:
            cid = ch.id
            db.execute(text("DELETE FROM submission_files WHERE submission_id IN (SELECT id FROM submissions WHERE challenge_id = :cid)"), {"cid": cid})
            db.execute(text("DELETE FROM evaluations WHERE submission_id IN (SELECT id FROM submissions WHERE challenge_id = :cid)"), {"cid": cid})
            db.execute(text("DELETE FROM submissions WHERE challenge_id = :cid"), {"cid": cid})
            db.execute(text("DELETE FROM chat_messages WHERE session_id IN (SELECT id FROM challenge_sessions WHERE challenge_id = :cid)"), {"cid": cid})
            db.execute(text("DELETE FROM challenge_sessions WHERE challenge_id = :cid"), {"cid": cid})
            db.execute(text("DELETE FROM challenge_files WHERE challenge_id = :cid"), {"cid": cid})
            db.execute(text("DELETE FROM challenges WHERE id = :cid"), {"cid": cid})
            db.commit()

        # Ensure test user exists
        u = db.query(User).filter(User.email == "mf_standalone@1code.com").first()
        if not u:
            u = User(name="MF User", email="mf_standalone@1code.com", password_hash="hash")
            db.add(u)
            db.commit()
            db.refresh(u)
        self.user_id = u.id
        db.close()

    def tearDown(self):
        pass


    @patch("routes.session.evaluate_submission_with_gemini")
    def test_multi_file_challenge_lifecycle_and_execution_gate(self, mock_eval):
        mock_eval.return_value = {
            "hypothesis": 20,
            "prompt_quality": 25,
            "ai_collaboration": 20,
            "code_correctness": 25,
            "problem_solving": 10,
            "total_score": 100,
            "strengths": ["Great multi-file fix"],
            "improvements": [],
            "overall_feedback": "All project files pass execution!"
        }
        # 1. Admin creates multi-file challenge

        payload = {
            "title": "Multi File Standalone Challenge",
            "slug": "test-mf-standalone-slug",
            "category": "Testing",
            "difficulty": "Easy",
            "time_limit": 30,
            "description": "Multi-file lifecycle test",
            "scenario": "Fix broken calculator imports across files",
            "rules": "All tests must pass",
            "run_command": "python test_calc.py",
            "files": [
                {
                    "filename": "calc.py",
                    "starter_content": "def add(a, b):\n    return a - b\n",
                    "solution_content": "def add(a, b):\n    return a + b\n",
                    "file_order": 0
                },
                {
                    "filename": "test_calc.py",
                    "starter_content": "from calc import add\ndef test_add():\n    assert add(2, 3) == 5\nif __name__ == '__main__':\n    test_add()\n    print('CALC TESTS PASSED')\n",
                    "solution_content": "from calc import add\ndef test_calc():\n    assert add(2, 3) == 5\nif __name__ == '__main__':\n    test_calc()\n    print('CALC TESTS PASSED')\n",
                    "file_order": 1
                }
            ]
        }
        res = client.post("/api/admin/challenges", json=payload, headers=ADMIN_HEADERS)
        self.assertEqual(res.status_code, 201)
        ch_data = res.json()
        self.assertIn("files", ch_data)
        self.assertEqual(len(ch_data["files"]), 2)
        self.assertEqual(ch_data["run_command"], "python test_calc.py")

        # 2. Start session
        s_res = client.post("/api/sessions/start", json={
            "challenge_id": ch_data["id"],
            "user_id": self.user_id,
            "name": "MF User",
            "hypothesis": "Broken subtraction operator in calc.py"
        })
        self.assertEqual(s_res.status_code, 201)
        session_id = s_res.json()["session_id"]

        # 3. Submit broken code -> Execution gate fails (passed = False)
        sub_fail = client.post(f"/api/sessions/{session_id}/submit", json={"actor_user_id": self.user_id})
        self.assertEqual(sub_fail.status_code, 200)
        res_fail = sub_fail.json()
        self.assertFalse(res_fail["passed"])
        self.assertNotEqual(res_fail["exit_code"], 0)
        self.assertIn("debug_log_path", res_fail)

        # 4. Save fixed project code
        fixed_files = {
            "calc.py": "def add(a, b):\n    return a + b\n",
            "test_calc.py": "from calc import add\ndef test_calc():\n    assert add(2, 3) == 5\nif __name__ == '__main__':\n    test_calc()\n    print('CALC TESTS PASSED')\n"
        }
        save_res = client.post(f"/api/sessions/{session_id}/save-code", json={
            "files": fixed_files,
            "actor_user_id": self.user_id
        })
        self.assertEqual(save_res.status_code, 200)

        # 5. Submit fixed code -> Execution gate passes (passed = True)
        sub_pass = client.post(f"/api/sessions/{session_id}/submit", json={"actor_user_id": self.user_id})
        self.assertEqual(sub_pass.status_code, 200)
        res_pass = sub_pass.json()
        self.assertTrue(res_pass["passed"])
        sub_id = res_pass["submission_id"]

        # 6. Verify SubmissionFile rows stored in PostgreSQL database
        db_check = SessionLocal()
        files_stored = db_check.query(SubmissionFile).filter(SubmissionFile.submission_id == sub_id).all()
        self.assertEqual(len(files_stored), 2)
        filenames = {f.filename for f in files_stored}
        self.assertIn("calc.py", filenames)
        self.assertIn("test_calc.py", filenames)
        db_check.close()


if __name__ == "__main__":
    unittest.main()
