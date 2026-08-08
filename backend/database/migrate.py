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
    "migration_team_mode.sql",
    "migration_teams.sql",
    "migration_team_sessions.sql",
    "migration_profile_activity.sql",
    "migration_perf_indexes.sql",
    "migration_user_ban.sql",
    "migration_site_visits.sql",
]

# Arbitrary constant, just needs to be unique to this app so it doesn't
# collide with an advisory lock used by something else on the same DB.
MIGRATION_LOCK_ID = 8743217


def run_migrations() -> None:
    migrations_dir = Path(__file__).resolve().parent
    with engine.connect() as conn:
        # Serializes migration runs across processes — if a second process
        # (e.g. an overlapping --reload restart) tries to run migrations
        # while another is still in progress, it blocks here and waits its
        # turn instead of racing on the same ALTER TABLE statements.
        conn.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": MIGRATION_LOCK_ID})
        try:
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
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": MIGRATION_LOCK_ID})


