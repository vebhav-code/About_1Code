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

    Enriches the response with submitter info (user_name, and team_name +
    members when team infrastructure exists) so the result page can display
    "Submitted by: Team XYZ (Alice, Bob)" or "Submitted by: Alice".
    """
    evaluation = db.query(Evaluation).filter(Evaluation.submission_id == submission_id).first()
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No evaluation found for submission ID {submission_id}."
        )

    # Build response dict from ORM object
    resp = EvaluationResponse.model_validate(evaluation)

    # --- Submitter info ---
    submission = evaluation.submission
    if submission:
        resp.user_name = submission.name

    # TODO: when the Team model is added, look up team_name and members here:
    #   team = db.query(Team).filter(Team.id == submission.team_id).first()
    #   if team:
    #       resp.team_name = team.name
    #       resp.members = [{"user_id": m.user_id, "name": m.name} for m in team.members]

    return resp

