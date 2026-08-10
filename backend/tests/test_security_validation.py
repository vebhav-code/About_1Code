import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.file_validation import FileValidationError, validate_challenge_slug, validate_challenge_filename
from services.execution_service import run_submission_code


class SecurityValidationTests(unittest.TestCase):
    def test_accepts_safe_challenge_slug(self):
        self.assertEqual(validate_challenge_slug("challenge-01"), "challenge-01")

    def test_rejects_path_traversal_slug(self):
        with self.assertRaises(FileValidationError):
            validate_challenge_slug("../evil")

    def test_accepts_safe_challenge_filename(self):
        self.assertEqual(validate_challenge_filename("api.py"), "api.py")
        self.assertEqual(validate_challenge_filename("utils/helpers.py"), "utils/helpers.py")

    def test_rejects_path_traversal_filename(self):
        invalid_filenames = [
            "../evil.py",
            "..\\evil.py",
            "/etc/passwd",
            "C:\\Windows\\System32\\cmd.exe",
            "foo/../../bar.py",
            "api.py\0.txt",
        ]
        for fn in invalid_filenames:
            with self.assertRaises(FileValidationError, msg=f"Should reject: {fn}"):
                validate_challenge_filename(fn)

    def test_sandbox_execution_blocks_path_traversal(self):
        malicious_files = {
            "../evil.py": "print('hacked')",
            "main.py": "print('ok')",
        }
        res = run_submission_code(malicious_files, run_command="python main.py")
        self.assertFalse(res["passed"])
        self.assertIn("Security validation error", res["stderr"])

    def test_sandbox_execution_timeout(self):
        infinite_loop_files = {
            "main.py": "import time\nwhile True:\n    time.sleep(1)\n"
        }
        res = run_submission_code(infinite_loop_files, run_command="python main.py", timeout_seconds=2)
        self.assertFalse(res["passed"])
        self.assertEqual(res["exit_code"], -1)
    def test_sandbox_execution_output_truncation(self):
        verbose_files = {
            "main.py": "print('A' * 60000)"
        }
        res = run_submission_code(verbose_files, run_command="python main.py")
        self.assertTrue(res["passed"])
        self.assertIn("[... output truncated ...]", res["stdout"])
        self.assertLessEqual(len(res["stdout"]), 50_100)


if __name__ == "__main__":
    unittest.main()

