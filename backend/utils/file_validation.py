"""
utils/file_validation.py
Validate uploaded files (type, size, contents).
"""

import re


class FileValidationError(Exception):
    """Raised when a file fails validation."""
    pass


def validate_challenge_slug(slug: str) -> str:
    """Ensure challenge slug is a safe, non-path-traversal identifier."""
    if not slug or not re.fullmatch(r"[A-Za-z0-9_-]+", slug):
        raise FileValidationError("Invalid challenge slug")
    return slug
