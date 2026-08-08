"""
routes/leaderboard.py
Leaderboard endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
from typing import List, Optional

from database.connection import get_db
from models.submission import Submission
from models.challenge import Challenge
from models.evaluation import Evaluation
from models.user import User
from models.team import Team
from models.team_member import TeamMember
from schemas.leaderboard import (
    LeaderboardEntryResponse,
    LeaderboardResponse,
    UserRankResponse,
    UserRankSummary,
    ChallengeStatsResponse
)

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("", response_model=LeaderboardResponse)
def get_leaderboard(
    challenge_slug: Optional[str] = None,
    mode: Optional[str] = "individual",
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get the top 100 ranked submissions for a SPECIFIC challenge filtered by mode ('individual' or 'team').
    Ordered by highest total score first, then by earlier submission time.
    Requires `challenge_slug`.
    """
    if not challenge_slug or not challenge_slug.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="challenge_slug is required"
        )

    challenge = db.query(Challenge).filter(Challenge.slug == challenge_slug.strip()).first()
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Challenge '{challenge_slug}' not found"
        )

    target_mode = mode.lower() if mode else "individual"

    query = db.query(
        Evaluation.submission_id,
        Submission.id.label("submission_id"),
        Submission.name.label("submission_name"),
        User.name.label("user_name"),
        Evaluation.total_score,
        Challenge.title.label("challenge_title"),
        Submission.submitted_at,
        Submission.team_id
    ).join(
        Submission, Evaluation.submission_id == Submission.id
    ).join(
        Challenge, Submission.challenge_id == Challenge.id
    ).outerjoin(
        User, Submission.user_id == User.id
    ).filter(
        Submission.challenge_id == challenge.id
    )

    if target_mode == "team":
        query = query.filter(Submission.team_id.isnot(None))
    else:
        query = query.filter(Submission.team_id.is_(None))

    results = query.order_by(
        desc(Evaluation.total_score),
        asc(Submission.submitted_at)
    ).limit(100).all()

    entry_list = []
    for index, row in enumerate(results, start=1):
        formatted_time = row.submitted_at.strftime("%Y-%m-%d %H:%M") if row.submitted_at else ""

        team_name = None
        members_list = None

        if target_mode == "team" and row.team_id:
            team_obj = db.query(Team).filter(Team.id == row.team_id).first()
            team_name = team_obj.name if team_obj else (row.submission_name or "Team")
            member_rows = (
                db.query(User.name)
                .join(TeamMember, TeamMember.user_id == User.id)
                .filter(TeamMember.team_id == row.team_id)
                .all()
            )
            members_list = [m[0] for m in member_rows if m[0]]

        entry_list.append(
            LeaderboardEntryResponse(
                rank=index,
                name=row.user_name if (row.user_name and target_mode != "team") else (team_name or row.submission_name or "Anonymous"),
                score=row.total_score,
                challenge=row.challenge_title,
                submission_time=formatted_time,
                team_name=team_name if target_mode == "team" else None,
                members=members_list if target_mode == "team" else None
            )
        )

    my_rank_info = None
    if user_id:
        # Check participation and rank for user_id in this challenge & mode
        all_challenge_subs = db.query(
            Evaluation.submission_id,
            Evaluation.total_score,
            Submission.submitted_at,
            Submission.user_id,
            Submission.team_id
        ).join(
            Submission, Evaluation.submission_id == Submission.id
        ).filter(
            Submission.challenge_id == challenge.id
        )

        if target_mode == "team":
            all_challenge_subs = all_challenge_subs.filter(Submission.team_id.isnot(None))
        else:
            all_challenge_subs = all_challenge_subs.filter(Submission.team_id.is_(None))

        ranked_all = all_challenge_subs.order_by(
            desc(Evaluation.total_score),
            asc(Submission.submitted_at)
        ).all()

        user_sub = None
        user_rank_idx = None

        for rank_idx, s in enumerate(ranked_all, start=1):
            if target_mode == "team":
                is_member = (
                    db.query(TeamMember)
                    .filter(TeamMember.team_id == s.team_id, TeamMember.user_id == user_id)
                    .first()
                )
                if is_member:
                    user_sub = s
                    user_rank_idx = rank_idx
                    break
            else:
                if s.user_id == user_id:
                    user_sub = s
                    user_rank_idx = rank_idx
                    break

        if user_sub and user_rank_idx:
            my_rank_info = UserRankSummary(
                participated=True,
                rank=user_rank_idx,
                score=user_sub.total_score,
                submission_id=user_sub.submission_id
            )
        else:
            my_rank_info = UserRankSummary(participated=False)

    return LeaderboardResponse(
        challenge_slug=challenge.slug,
        challenge_title=challenge.title,
        mode=target_mode,
        entries=entry_list,
        my_rank=my_rank_info
    )


import time

# In-process TTL cache for GET /api/leaderboard/stats (TTL ~20s per challenge_slug).
# NOTE: This cache is stored in-memory within this single process. If the backend is ever
# horizontally scaled to multiple worker processes/instances, replace this with a centralized
# Redis cache (similar to the in-memory WebSocket connection registry note in team_ws.py).
_stats_cache = {}
_STATS_CACHE_TTL = 20.0  # seconds


@router.get("/stats", response_model=List[ChallengeStatsResponse])
def get_leaderboard_stats(challenge_slug: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Get statistics for a specific challenge (requires challenge_slug).
    """
    if not challenge_slug or not challenge_slug.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="challenge_slug is required"
        )

    slug_key = challenge_slug.strip()
    now = time.time()
    if slug_key in _stats_cache:
        cached_data, expiry = _stats_cache[slug_key]
        if now < expiry:
            return cached_data

    challenge = db.query(Challenge).filter(Challenge.slug == slug_key).first()
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Challenge '{challenge_slug}' not found",
        )

    query = db.query(
        Challenge.title.label("challenge_name"),
        func.count(Evaluation.id).label("total_participants"),
        func.avg(Evaluation.total_score).label("average_score"),
        func.max(Evaluation.total_score).label("highest_score"),
        func.min(Evaluation.total_score).label("lowest_score"),
        Challenge.slug.label("challenge_slug")
    ).join(
        Submission, Submission.challenge_id == Challenge.id
    ).join(
        Evaluation, Evaluation.submission_id == Submission.id
    ).filter(
        Challenge.id == challenge.id
    ).group_by(Challenge.id)

    result = query.all()

    stats_list = []
    for row in result:
        stats_list.append(
            ChallengeStatsResponse(
                total_participants=row.total_participants,
                average_score=round(float(row.average_score), 2) if row.average_score is not None else 0.0,
                highest_score=row.highest_score if row.highest_score is not None else 0,
                lowest_score=row.lowest_score if row.lowest_score is not None else 0,
                challenge_name=row.challenge_name,
                challenge_slug=row.challenge_slug
            )
        )

    if not stats_list:
        stats_list = [
            ChallengeStatsResponse(
                total_participants=0,
                average_score=0.0,
                highest_score=0,
                lowest_score=0,
                challenge_name=challenge.title,
                challenge_slug=challenge.slug
            )
        ]

    _stats_cache[slug_key] = (stats_list, now + _STATS_CACHE_TTL)
    return stats_list


@router.get("/{submission_id}", response_model=UserRankResponse)
def get_user_rank(submission_id: int, db: Session = Depends(get_db)):
    """
    Get current rank for a specific submission along with adjacent users above and below.
    Calculates ranks dynamically using database window functions.
    """
    # 1. Define Common Table Expression or subquery to rank all evaluations
    rank_subquery = db.query(
        Evaluation.submission_id,
        Evaluation.total_score,
        Submission.submitted_at,
        User.name.label("user_name"),
        Challenge.title.label("challenge_title"),
        func.row_number().over(
            order_by=(desc(Evaluation.total_score), asc(Submission.submitted_at))
        ).label("rank")
    ).join(
        Submission, Evaluation.submission_id == Submission.id
    ).join(
        Challenge, Submission.challenge_id == Challenge.id
    ).outerjoin(
        User, Submission.user_id == User.id
    ).subquery()

    # 2. Get the target submission rank
    target = db.query(rank_subquery).filter(rank_subquery.c.submission_id == submission_id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation for submission ID {submission_id} not found"
        )

    current_rank = target.rank
    current_score = target.total_score

    # 3. Retrieve adjacent ranks (up to 3 above, up to 3 below)
    results_above = db.query(rank_subquery).filter(
        rank_subquery.c.rank < current_rank
    ).order_by(desc(rank_subquery.c.rank)).limit(3).all()
    # Reverse so it lists top-down (e.g. rank 2, then rank 3)
    results_above = sorted(results_above, key=lambda x: x.rank)

    results_below = db.query(rank_subquery).filter(
        rank_subquery.c.rank > current_rank
    ).order_by(asc(rank_subquery.c.rank)).limit(3).all()

    # Helper function to map database subquery rows to LeaderboardEntryResponse schema
    def map_row_to_schema(row) -> LeaderboardEntryResponse:
        formatted_time = row.submitted_at.strftime("%Y-%m-%d %H:%M") if row.submitted_at else ""
        return LeaderboardEntryResponse(
            rank=row.rank,
            name=row.user_name if row.user_name else "Anonymous",
            score=row.total_score,
            challenge=row.challenge_title,
            submission_time=formatted_time
        )

    return UserRankResponse(
        current_rank=current_rank,
        current_score=current_score,
        users_above=[map_row_to_schema(r) for r in results_above],
        users_below=[map_row_to_schema(r) for r in results_below]
    )
