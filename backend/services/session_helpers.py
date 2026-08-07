"""
services/session_helpers.py
Shared helpers for individual and team session initializations.
"""

from models.challenge import Challenge


def load_starter_code(challenge: Challenge) -> str:
    """Load starter code for a challenge."""
    return challenge.starter_code or ""
