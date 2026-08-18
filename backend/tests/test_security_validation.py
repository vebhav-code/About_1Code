import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.file_validation import FileValidationError, validate_challenge_slug, validate_challenge_filename


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


if __name__ == "__main__":
    unittest.main()
