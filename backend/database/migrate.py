"""Apply idempotent SQL migrations on startup."""
from pathlib import Path

from sqlalchemy import text

from database.connection import engine

MIGRATION_FILES = [
    "migration.sql",
    "migration_leaderboard.sql",
    "migration_submissions.sql",
    "migration_admin.sql",
    "migration_sessions.sql",
    "migration_rules.sql",
    "migration_late_flag.sql",
    "migration_challenge_content.sql",
    "migration_session_user.sql",
    "migration_session_hypothesis.sql",
]


def run_migrations() -> None:
    migrations_dir = Path(__file__).resolve().parent
    with engine.connect() as conn:
        for filename in MIGRATION_FILES:
            path = migrations_dir / filename
            if not path.exists():
                continue
            sql = path.read_text(encoding="utf-8")
            for statement in sql.split(";"):
                statement = statement.strip()
                if statement:
                    conn.execute(text(statement))
        conn.commit()
