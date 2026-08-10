"""
services/session_helpers.py
Shared helpers for individual and team session initializations.
"""

import json
from models.challenge import Challenge


def load_starter_code(challenge: Challenge) -> str:
    """Load starter code for a challenge, handling multi-file and legacy single-file."""
    if hasattr(challenge, "challenge_format") and challenge.challenge_format == "build":
        return json.dumps({})
    if hasattr(challenge, "files") and challenge.files:
        files_dict = {
            f.filename: f.starter_content
            for f in sorted(challenge.files, key=lambda x: x.file_order)
        }
        return json.dumps(files_dict)
    return challenge.starter_code or ""

