import logging
from datetime import date, timedelta
from sqlalchemy.orm import Session

from models.user import User
from models.user_activity import UserActivity

logger = logging.getLogger(__name__)


def record_visit(db: Session, user_id: int) -> None:
    """
    Idempotently records a user's daily visit, recomputes current & longest streak,
    and updates last_active_date on the User record.
    """
    today = date.today()

    # 1. Record today's visit if not present
    existing = (
        db.query(UserActivity)
        .filter(UserActivity.user_id == user_id, UserActivity.visit_date == today)
        .first()
    )
    if not existing:
        try:
            visit = UserActivity(user_id=user_id, visit_date=today)
            db.add(visit)
            db.commit()
        except Exception as e:
            db.rollback()
            # In case of race conditions, re-check
            existing = (
                db.query(UserActivity)
                .filter(UserActivity.user_id == user_id, UserActivity.visit_date == today)
                .first()
            )
            if not existing:
                logger.warning(f"Failed to record visit for user {user_id}: {e}")

    # 2. Fetch all recorded visit dates for streak calculation
    rows = (
        db.query(UserActivity.visit_date)
        .filter(UserActivity.user_id == user_id)
        .all()
    )
    visited_dates = {r[0] for r in rows if r[0]}
    visited_dates.add(today)  # Ensure today is present

    # 3. Calculate current_streak (consecutive days backward from today)
    current_streak = 0
    check_date = today
    while check_date in visited_dates:
        current_streak += 1
        check_date = check_date - timedelta(days=1)

    # 4. Calculate longest_streak across all historical visits
    sorted_dates = sorted(visited_dates)
    max_streak = 0
    curr_run = 0
    prev_d = None
    for d in sorted_dates:
        if prev_d is None or d == prev_d + timedelta(days=1):
            curr_run += 1
        else:
            curr_run = 1
        prev_d = d
        if curr_run > max_streak:
            max_streak = curr_run

    # 5. Update user model
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.current_streak = current_streak
        user.longest_streak = max(max_streak, user.longest_streak or 0)
        user.last_active_date = today
        db.commit()
