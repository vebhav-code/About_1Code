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
from schemas.leaderboard import (
    LeaderboardEntryResponse,
    UserRankResponse,
    ChallengeStatsResponse
)

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("", response_model=List[LeaderboardEntryResponse])
def get_leaderboard(db: Session = Depends(get_db)):
    """
    Get the top 100 ranked submissions.
    Ordered by highest total score first, then by earlier submission time.
    """
    results = db.query(
        Evaluation.submission_id,
        User.name.label("user_name"),
        Evaluation.total_score,
        Challenge.title.label("challenge_title"),
        Submission.submitted_at
    ).join(
        Submission, Evaluation.submission_id == Submission.id
    ).join(
        Challenge, Submission.challenge_id == Challenge.id
    ).outerjoin(
        User, Submission.user_id == User.id
    ).order_by(
        desc(Evaluation.total_score),
        asc(Submission.submitted_at)
    ).limit(100).all()

    entry_list = []
    for index, row in enumerate(results, start=1):
        formatted_time = row.submitted_at.strftime("%Y-%m-%d %H:%M") if row.submitted_at else ""
        entry_list.append(
            LeaderboardEntryResponse(
                rank=index,
                name=row.user_name if row.user_name else "Anonymous",
                score=row.total_score,
                challenge=row.challenge_title,
                submission_time=formatted_time
            )
        )
    return entry_list


@router.get("/stats", response_model=List[ChallengeStatsResponse])
def get_leaderboard_stats(challenge_slug: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Get statistics per challenge (or for a specific challenge if slug is provided).
    Calculates total participants, average, highest, and lowest scores.
    """
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
    ).group_by(Challenge.id)

    if challenge_slug:
        if not db.query(Challenge).filter(Challenge.slug == challenge_slug).first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Challenge '{challenge_slug}' not found",
            )
        query = query.filter(Challenge.slug == challenge_slug)

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
