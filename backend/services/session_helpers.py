"""
services/session_helpers.py
Shared helpers for individual and team session initializations.
"""

from models.challenge import Challenge


def load_starter_code(challenge: Challenge) -> str:
    """Return initial starter approach text for a challenge (default empty)."""
    return ""
