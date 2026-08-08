from datetime import datetime, timezone, date, timedelta

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from models.challenge import Challenge
from models.chat_message import ChatMessage
from models.session import ChallengeSession
from models.submission import Submission
from models.team import Team
from models.team_member import TeamMember
from models.user import User
from models.user_activity import UserActivity

DIFFICULTY_WEIGHTS = {"Easy": 1.0, "Medium": 1.5, "Hard": 2.0}


def _user_submissions(db: Session, user_id: int):
    """All submissions this user is credited for — individual or via a team they were on."""
    team_ids = [m.team_id for m in db.query(TeamMember).filter(TeamMember.user_id == user_id).all()]
    query = db.query(Submission)
    if team_ids:
        query = query.filter(or_(Submission.user_id == user_id, Submission.team_id.in_(team_ids)))
    else:
        query = query.filter(Submission.user_id == user_id)
    return query.all()


def _all_users_weighted_points(db: Session) -> dict[int, float]:
    weight_case = case(
        (Challenge.difficulty == "Easy", 1.0),
        (Challenge.difficulty == "Medium", 1.5),
        (Challenge.difficulty == "Hard", 2.0),
        else_=1.0,
    )

    individual = (
        db.query(
            Submission.user_id.label("uid"),
            (func.coalesce(Submission.overall_score, 0) * weight_case).label("points"),
        )
        .join(Challenge, Challenge.id == Submission.challenge_id)
        .filter(Submission.user_id.isnot(None))
    )

    team = (
        db.query(
            TeamMember.user_id.label("uid"),
            (func.coalesce(Submission.overall_score, 0) * weight_case).label("points"),
        )
        .select_from(Submission)
        .join(Challenge, Challenge.id == Submission.challenge_id)
        .join(TeamMember, TeamMember.team_id == Submission.team_id)
        .filter(Submission.team_id.isnot(None))
    )

    combined = individual.union_all(team).subquery()

    totals = (
        db.query(combined.c.uid, func.sum(combined.c.points).label("total"))
        .group_by(combined.c.uid)
        .all()
    )
    return {uid: round(total, 1) for uid, total in totals}


def _compute_active_days(db: Session, user_id: int) -> int:
    dates = set()
    for row in db.query(ChallengeSession.started_at).filter(ChallengeSession.user_id == user_id).all():
        if row[0]:
            dates.add(row[0].date())
    for row in db.query(ChatMessage.created_at).filter(ChatMessage.user_id == user_id).all():
        if row[0]:
            dates.add(row[0].date())
    for row in db.query(Submission.submitted_at).filter(Submission.user_id == user_id).all():
        if row[0]:
            dates.add(row[0].date())
    return len(dates)


def _compute_visit_calendar(db: Session, user_id: int) -> list[dict]:
    today = date.today()
    start_date = today - timedelta(days=89)
    rows = (
        db.query(UserActivity.visit_date)
        .filter(UserActivity.user_id == user_id, UserActivity.visit_date >= start_date)
        .all()
    )
    active_dates = {r[0] for r in rows if r[0]}

    calendar = []
    for i in range(89, -1, -1):
        d = today - timedelta(days=i)
        calendar.append({
            "date": d.isoformat(),
            "active": d in active_dates,
        })
    return calendar


def _compute_badges(submissions: list, challenges_by_id: dict) -> list[dict]:
    badges = []
    count = len(submissions)
    if count >= 1:
        badges.append({"name": "First Submission", "description": "Completed your first challenge"})
    if count >= 5:
        badges.append({"name": "5 Submissions", "description": "Completed 5 challenges"})
    if count >= 10:
        badges.append({"name": "10 Submissions", "description": "Completed 10 challenges"})
    if any((submission.overall_score or 0) >= 95 for submission in submissions):
        badges.append({"name": "Perfectionist", "description": "Scored 95+ on a challenge"})
    if any(submission.team_id is not None for submission in submissions):
        badges.append({"name": "Team Player", "description": "Completed a challenge as part of a team"})

    categories = set()
    for submission in submissions:
        challenge = challenges_by_id.get(submission.challenge_id)
        if challenge and challenge.category:
            categories.add(challenge.category)
    if len(categories) >= 3:
        badges.append({"name": "Well-Rounded", "description": "Completed challenges across 3+ categories"})
    return badges


def _compute_difficulty_breakdown(db: Session, user_id: int, submissions: list) -> dict:
    solved_challenge_ids = {s.challenge_id for s in submissions if s.challenge_id}
    all_challenges = db.query(Challenge).filter(Challenge.is_active == True).all()

    breakdown = {
        "Easy": {"solved": 0, "total": 0},
        "Medium": {"solved": 0, "total": 0},
        "Hard": {"solved": 0, "total": 0},
    }

    for challenge in all_challenges:
        diff = challenge.difficulty or "Easy"
        if diff not in breakdown:
            breakdown[diff] = {"solved": 0, "total": 0}
        breakdown[diff]["total"] += 1
        if challenge.id in solved_challenge_ids:
            breakdown[diff]["solved"] += 1

    return breakdown


def get_user_profile(db: Session, user_id: int) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    user_id_value = user.id
    user_name = user.name
    user_created_at = user.created_at

    submissions = _user_submissions(db, user_id)
    challenge_ids = {s.challenge_id for s in submissions if s.challenge_id}
    challenges_by_id = {
        c.id: c for c in db.query(Challenge).filter(Challenge.id.in_(challenge_ids)).all()
    } if challenge_ids else {}

    total_attempted = db.query(func.count(ChallengeSession.id)).filter(ChallengeSession.user_id == user_id).scalar() or 0
    total_completed = len(submissions)
    avg_score = round(sum(submission.overall_score or 0 for submission in submissions) / total_completed, 1) if total_completed else 0
    best_score = max((submission.overall_score or 0 for submission in submissions), default=0)

    category_scores: dict[str, list[int]] = {}
    for submission in submissions:
        challenge = challenges_by_id.get(submission.challenge_id)
        if challenge:
            category_scores.setdefault(challenge.category or "Other", []).append(submission.overall_score or 0)

    category_breakdown = [
        {"category": category, "average_score": round(sum(scores) / len(scores), 1), "count": len(scores)}
        for category, scores in category_scores.items()
    ]

    all_points = _all_users_weighted_points(db)
    points_by_user = sorted(all_points.items(), key=lambda kv: kv[1], reverse=True)
    rank = next((i + 1 for i, (uid, _) in enumerate(points_by_user) if uid == user_id), None)
    percentile = round((1 - (rank - 1) / len(points_by_user)) * 100) if rank and points_by_user else None
    weighted_points = all_points.get(user_id, 0.0)

    history = []
    for submission in sorted(submissions, key=lambda item: item.submitted_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        challenge = challenges_by_id.get(submission.challenge_id)
        history.append({
            "submission_id": submission.id,
            "challenge_title": challenge.title if challenge else "Unknown",
            "difficulty": challenge.difficulty if challenge else None,
            "mode": "team" if submission.team_id else "individual",
            "score": submission.overall_score,
            "late": submission.late,
            "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
        })

    return {
        "user_id": user_id_value,
        "name": user_name,
        "joined_at": user_created_at.isoformat() if user_created_at else None,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "github_url": getattr(user, "github_url", "") or "",
        "linkedin_url": getattr(user, "linkedin_url", "") or "",
        "website_url": getattr(user, "website_url", "") or "",
        "current_streak": user.current_streak or 0,
        "longest_streak": user.longest_streak or 0,
        "last_active_date": user.last_active_date.isoformat() if user.last_active_date else None,
        "visit_calendar": _compute_visit_calendar(db, user_id),
        "difficulty_breakdown": _compute_difficulty_breakdown(db, user_id, submissions),
        "total_attempted": total_attempted,
        "total_completed": total_completed,
        "average_score": avg_score,
        "best_score": best_score,
        "weighted_points": weighted_points,
        "rank": rank,
        "percentile": percentile,
        "active_days": _compute_active_days(db, user_id),
        "category_breakdown": category_breakdown,
        "badges": _compute_badges(submissions, challenges_by_id),
        "history": history,
    }


