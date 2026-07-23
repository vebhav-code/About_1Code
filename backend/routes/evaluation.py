"""
routes/evaluation.py
Evaluation read routes.
The POST /evaluate endpoint (zip-extraction path) has been removed.
Evaluation is now created inline by routes/session.py on submit.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.connection import get_db
from models.evaluation import Evaluation
from schemas.evaluation import EvaluationResponse

router = APIRouter(prefix="/api", tags=["evaluation"])
logger = logging.getLogger(__name__)


@router.get("/evaluate/{submission_id}", response_model=EvaluationResponse)
def get_evaluation(
    submission_id: int,
    db: Session = Depends(get_db)
):
    """
    Retrieve an existing evaluation for a submission.
    Returns 404 if no evaluation has been created yet.
    """
    evaluation = db.query(Evaluation).filter(Evaluation.submission_id == submission_id).first()
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No evaluation found for submission ID {submission_id}."
        )
    return evaluation

