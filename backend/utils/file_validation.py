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


ALLOWED_AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def validate_avatar_file(filename: str, content_type: str = None, file_size: int = None) -> None:
    """Validate uploaded avatar image extension and size."""
    if not filename:
        raise FileValidationError("No filename provided")

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        raise FileValidationError(
            f"Invalid avatar image file format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_AVATAR_EXTENSIONS))}"
        )

    if content_type and not content_type.startswith("image/"):
        raise FileValidationError(f"Invalid content type '{content_type}'. Must be an image.")

    if file_size is not None and file_size > MAX_AVATAR_SIZE_BYTES:
        raise FileValidationError(
            f"File size exceeds maximum allowed limit of {MAX_AVATAR_SIZE_BYTES // (1024 * 1024)} MB"
        )

