"""Apply idempotent SQL migrations on startup."""
import logging
import time
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from database.connection import engine

logger = logging.getLogger(__name__)

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
    "migration_multi_file_challenges.sql",
    "migration_challenge_format.sql",
    "migration_team_join_requests.sql",
    "migration_indexes.sql",
    "migration_remove_multi_file.sql",
    "migration_approach_mode.sql",
]

# Arbitrary constant, just needs to be unique to this app so it doesn't
# collide with an advisory lock used by something else on the same DB.
MIGRATION_LOCK_ID = 8743217


def _execute_statement_with_retry(conn, statement: str, max_retries: int = 3) -> None:
    """Execute a single DDL statement with retries to handle transient lock contention during hot reload."""
    for attempt in range(max_retries):
        try:
            conn.execute(text(statement))
            return
        except OperationalError as e:
            if "deadlock detected" in str(e).lower() or "lock timeout" in str(e).lower():
                if attempt < max_retries - 1:
                    time.sleep(0.2 * (attempt + 1))
                    continue
            logger.warning("Migration statement failed: %s (error: %s)", statement, e)
            raise


def run_migrations() -> None:
    migrations_dir = Path(__file__).resolve().parent
    with engine.connect() as conn:
        is_postgres = conn.dialect.name == "postgresql"
        if is_postgres:
            try:
                conn.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": MIGRATION_LOCK_ID})
                conn.commit()
            except Exception as e:
                logger.warning("Could not acquire migration advisory lock: %s", e)

        try:
            # 1. Create tracking table if it doesn't exist yet
            if is_postgres:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        filename VARCHAR PRIMARY KEY,
                        applied_at TIMESTAMPTZ DEFAULT now()
                    )
                """))
            else:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        filename VARCHAR PRIMARY KEY,
                        applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
            conn.commit()

            # 2. Query already applied migration filenames
            already_applied = {
                row[0] for row in conn.execute(text("SELECT filename FROM schema_migrations")).fetchall()
            }

            pending = [f for f in MIGRATION_FILES if f not in already_applied]

            if not pending:
                print(f"No pending migrations — skipped all {len(MIGRATION_FILES)} files.")
                return

            print(f"Running {len(pending)} pending migration(s): {pending}")

            # 3. Execute each pending migration file
            for filename in pending:
                path = migrations_dir / filename
                if not path.exists():
                    continue
                sql = path.read_text(encoding="utf-8")
                for statement in sql.split(";"):
                    statement = statement.strip()
                    if statement:
                        try:
                            _execute_statement_with_retry(conn, statement)
                            conn.commit()
                        except Exception as err:
                            conn.rollback()
                            if "already exists" in str(err).lower():
                                continue
                            logger.error("Failed executing migration statement in %s: %s", filename, err)
                
                # Record the migration as applied
                try:
                    if is_postgres:
                        conn.execute(
                            text("INSERT INTO schema_migrations (filename) VALUES (:f) ON CONFLICT DO NOTHING"),
                            {"f": filename},
                        )
                    else:
                        conn.execute(
                            text("INSERT OR IGNORE INTO schema_migrations (filename) VALUES (:f)"),
                            {"f": filename},
                        )
                    conn.commit()
                except Exception as record_err:
                    conn.rollback()
                    logger.warning("Could not record migration %s in schema_migrations: %s", filename, record_err)
        finally:
            if is_postgres:
                try:
                    conn.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": MIGRATION_LOCK_ID})
                    conn.commit()
                except Exception:
                    pass



