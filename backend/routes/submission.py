"""
routes/submission.py
Submission read routes.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from database.connection import get_db
from models.challenge import Challenge
from models.evaluation import Evaluation
from models.submission import Submission
from models.user import User

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


@router.get("")
def list_submissions(db: Session = Depends(get_db)) -> List[dict]:
    """List all submissions for the admin studio."""
    submissions = (
        db.query(Submission, Challenge, Evaluation, User)
        .join(Challenge, Submission.challenge_id == Challenge.id)
        .outerjoin(Evaluation, Evaluation.submission_id == Submission.id)
        .outerjoin(User, Submission.user_id == User.id)
        .order_by(desc(Submission.submitted_at))
        .all()
    )
    records = []
    for submission, challenge, evaluation, user in submissions:
        score = evaluation.total_score if evaluation else submission.overall_score
        status_label = "evaluated" if evaluation else ("scored" if submission.overall_score else "pending")
        records.append(
            {
                "id": submission.id,
                "challenge_slug": challenge.slug,
                "score": score,
                "created_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
                "status": status_label,
                "name": user.name if user else submission.name,
            }
        )
    return records


@router.get("/{submission_id}")
def get_submission_result(submission_id: int, db: Session = Depends(get_db)):
    result = (
        db.query(Submission, User)
        .outerjoin(User, Submission.user_id == User.id)
        .filter(Submission.id == submission_id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Submission not found")
    submission, user = result
    display_name = user.name if user else submission.name
    return {
        "submission_id": submission.id,
        "name": display_name,
        "late": getattr(submission, "late", False),
        "problem_understanding_score": submission.problem_understanding_score,
        "prompt_quality_score": submission.prompt_quality_score,
        "ai_collaboration_score": submission.ai_collaboration_score,
        "code_correctness_score": submission.code_correctness_score,
        "overall_score": submission.overall_score,
        "feedback": submission.feedback,
        "submitted_at": submission.submitted_at,
    }
