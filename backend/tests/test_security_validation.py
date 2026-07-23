import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.file_validation import FileValidationError, validate_challenge_slug


class SecurityValidationTests(unittest.TestCase):
    def test_accepts_safe_challenge_slug(self):
        self.assertEqual(validate_challenge_slug("challenge-01"), "challenge-01")

    def test_rejects_path_traversal_slug(self):
        with self.assertRaises(FileValidationError):
            validate_challenge_slug("../evil")


if __name__ == "__main__":
    unittest.main()
