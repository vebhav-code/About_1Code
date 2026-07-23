"""
routes/session.py
Session-based challenge workspace routes.
Replaces the zip-upload flow with a server-tracked session + live editor + chat.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.connection import get_db
from models.challenge import Challenge
from models.chat_message import ChatMessage
from models.evaluation import Evaluation
from models.session import ChallengeSession
from models.submission import Submission
from services.gemini_service import (
    chat_with_gemini,
    evaluate_submission_with_gemini,
    read_official_solution,
    read_source_files,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Pydantic request bodies
# ---------------------------------------------------------------------------

class StartRequest(BaseModel):
    challenge_id: int
    user_id: int
    name: str
    hypothesis: str


class ChatRequest(BaseModel):
    message: str


class SaveCodeRequest(BaseModel):
    code: str


# ---------------------------------------------------------------------------
# Helper — load starter code from assets
# ---------------------------------------------------------------------------

def _load_starter_code(challenge: Challenge) -> str:
    return challenge.starter_code or ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/start", status_code=status.HTTP_201_CREATED)
def start_session(body: StartRequest, db: Session = Depends(get_db)):
    """
    Create a new ChallengeSession row.
    Seeds current_code with the challenge's buggy project starter files.
    Returns session_id + starter_code.
    """
    challenge = db.query(Challenge).filter(Challenge.id == body.challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    existing_submission = (
        db.query(Submission)
        .filter(Submission.user_id == body.user_id, Submission.challenge_id == body.challenge_id)
        .first()
    )
    if existing_submission:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You've already submitted this challenge. Each challenge can only be attempted once.",
        )

    starter_code = _load_starter_code(challenge)

    session = ChallengeSession(
        challenge_id=challenge.id,
        user_id=body.user_id,
        name=body.name.strip() or "Anonymous",
        hypothesis=body.hypothesis.strip(),
        current_code=starter_code,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "session_id": session.id,
        "starter_code": starter_code,
        "challenge": {
            "title": challenge.title,
            "scenario": challenge.scenario,
            "time_limit": challenge.time_limit,
        },
    }


@router.post("/{session_id}/chat")
async def send_message(
    session_id: int,
    body: ChatRequest,
    db: Session = Depends(get_db),
):
    """
    Save the user's message, call Gemini with a helper persona,
    save the assistant reply, and return it to the frontend.
    """
    session = db.query(ChallengeSession).filter(ChallengeSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.submitted_at is not None:
        raise HTTPException(status_code=400, detail="Session already submitted")

    challenge = db.query(Challenge).filter(Challenge.id == session.challenge_id).first()

    # 1. Persist user message (commit before Gemini so it's never lost on API errors)
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=body.message,
    )
    db.add(user_msg)
    db.commit()

    # 2. Call Gemini
    reply_text = await chat_with_gemini(
        scenario=challenge.scenario or "",
        current_code=session.current_code,
        message=body.message,
    )

    # 3. Persist assistant message
    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=reply_text,
    )
    db.add(assistant_msg)
    db.commit()

    return {"reply": reply_text}


@router.post("/{session_id}/save-code")
def save_code(
    session_id: int,
    body: SaveCodeRequest,
    db: Session = Depends(get_db),
):
    """Update ChallengeSession.current_code. Called on an interval from the editor."""
    session = db.query(ChallengeSession).filter(ChallengeSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.submitted_at is not None:
        raise HTTPException(status_code=400, detail="Session already submitted")

    session.current_code = body.code
    db.commit()
    return {"saved": True}


@router.post("/{session_id}/submit")
async def submit_session(session_id: int, db: Session = Depends(get_db)):
    """
    Mark the session as submitted, evaluate the code + chat transcript with
    Gemini, store a Submission + Evaluation row, and return submission_id.
    """
    session = db.query(ChallengeSession).filter(ChallengeSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.submitted_at is not None:
        raise HTTPException(status_code=400, detail="Session already submitted")

    challenge = db.query(Challenge).filter(Challenge.id == session.challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    # 0. Compute whether the submission is late
    started_at = session.started_at
    if started_at:
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        elapsed_minutes = (datetime.now(timezone.utc) - started_at).total_seconds() / 60
    else:
        elapsed_minutes = 0.0

    time_limit = challenge.time_limit or 45
    is_late = elapsed_minutes > time_limit

    # 1. Mark submitted
    session.submitted_at = datetime.now(timezone.utc)
    db.flush()

    # 2. Assemble chat transcript
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    transcript_parts = [
        f"[{msg.role.upper()}]: {msg.content}"
        for msg in messages
    ]
    chat_transcript = "\n\n".join(transcript_parts) if transcript_parts else "(no chat messages)"

    # 3. Read official solution
    try:
        official_solution = read_official_solution(challenge)
    except Exception:
        official_solution = "No official solution reference is available for this challenge."

    # 4. Evaluate with Gemini
    try:
        gemini_result = await evaluate_submission_with_gemini(
            submission=None,
            challenge=challenge,
            db_log_content=chat_transcript,
            user_code_content=session.current_code or "(no code submitted)",
            official_solution_content=official_solution,
            hypothesis_content=session.hypothesis or "(no hypothesis provided)",
            is_late=is_late,
            elapsed_minutes=elapsed_minutes,
        )
    except Exception as e:
        db.rollback()
        logger.exception("Gemini evaluation failed during session submit")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Evaluation failed: {str(e)}",
        )

    # 5. Store Submission
    submission = Submission(
        name=session.name,
        user_id=session.user_id,
        challenge_id=challenge.id,
        fixed_project_path=None,
        debug_log_path=None,
        late=is_late,
        problem_understanding_score=gemini_result.get("problem_solving", 0),
        prompt_quality_score=gemini_result.get("prompt_quality", 0),
        ai_collaboration_score=gemini_result.get("ai_collaboration", 0),
        code_correctness_score=gemini_result.get("code_correctness", 0),
        overall_score=gemini_result.get("total_score", 0),
        feedback=gemini_result.get("overall_feedback", ""),
    )
    db.add(submission)
    db.flush()

    # 6. Store Evaluation
    evaluation = Evaluation(
        submission_id=submission.id,
        hypothesis=gemini_result.get("hypothesis", 0),
        prompt_quality=gemini_result.get("prompt_quality", 0),
        ai_collaboration=gemini_result.get("ai_collaboration", 0),
        code_correctness=gemini_result.get("code_correctness", 0),
        problem_solving=gemini_result.get("problem_solving", 0),
        total_score=gemini_result.get("total_score", 0),
        strengths=gemini_result.get("strengths", []),
        improvements=gemini_result.get("improvements", []),
        overall_feedback=gemini_result.get("overall_feedback", ""),
    )
    db.add(evaluation)
    db.commit()

    return {"submission_id": submission.id}
