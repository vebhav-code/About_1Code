"""
routes/session.py
Session-based challenge workspace routes.
Replaces the zip-upload flow with a server-tracked session + live editor + chat.
Generalised for both individual and team mode sessions.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.connection import get_db
from models.challenge import Challenge
from models.chat_message import ChatMessage
from models.evaluation import Evaluation
from models.session import ChallengeSession
from models.submission import Submission
from models.team import Team
from models.team_member import TeamMember
from models.user import User
from routes.team_ws import broadcast_to_team
from services.gemini_service import (
    chat_with_gemini,
    evaluate_submission_with_gemini,
    read_official_solution,
    read_source_files,
)
from services.session_helpers import load_starter_code

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
    actor_user_id: Optional[int] = None


class SaveCodeRequest(BaseModel):
    code: str
    actor_user_id: Optional[int] = None


class SubmitRequest(BaseModel):
    actor_user_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Authorization Helper
# ---------------------------------------------------------------------------

def _authorize_session_actor(session: ChallengeSession, user_id: Optional[int], db: Session) -> None:
    """
    Ensure the actor is authorized to interact with the session.
    If individual session: user_id can match or be unenforced for backward compatibility.
    If team session: actor_user_id MUST be provided and MUST be a member of the team.
    """
    if session.team_id is not None:
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="actor_user_id is required for team session operations.",
            )
        member = (
            db.query(TeamMember)
            .filter(TeamMember.team_id == session.team_id, TeamMember.user_id == user_id)
            .first()
        )
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this team.",
            )
    else:
        if user_id is not None and session.user_id is not None and user_id != session.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized for this individual session.",
            )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/start", status_code=status.HTTP_201_CREATED)
def start_session(body: StartRequest, db: Session = Depends(get_db)):
    """
    Create a new individual ChallengeSession row.
    Seeds current_code with the challenge's buggy project starter files.
    Returns session_id + starter_code.
    """
    user = db.query(User).filter(User.id == body.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found — your session may be from a different environment. Please log in again.",
        )

    challenge = db.query(Challenge).filter(Challenge.id == body.challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    if challenge.mode == "team":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This challenge is team-only. Join or create a team to attempt it.",
        )

    existing_submission = (
        db.query(Submission)
        .outerjoin(TeamMember, TeamMember.team_id == Submission.team_id)
        .filter(
            Submission.challenge_id == body.challenge_id,
            (Submission.user_id == body.user_id) | (TeamMember.user_id == body.user_id),
        )
        .first()
    )
    if existing_submission:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You've already submitted this challenge. Each challenge can only be attempted once.",
        )

    starter_code = load_starter_code(challenge)

    session = ChallengeSession(
        challenge_id=challenge.id,
        user_id=body.user_id,
        team_id=None,
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
    Broadcasting over WebSocket if team session.
    """
    session = db.query(ChallengeSession).filter(ChallengeSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.submitted_at is not None:
        raise HTTPException(status_code=400, detail="Session already submitted")

    _authorize_session_actor(session, body.actor_user_id, db)

    challenge = db.query(Challenge).filter(Challenge.id == session.challenge_id).first()

    # 1. Persist user message
    user_msg = ChatMessage(
        session_id=session_id,
        user_id=body.actor_user_id,
        role="user",
        content=body.message,
    )
    db.add(user_msg)
    db.commit()

    # Get actor name for broadcast if available
    actor_name = "Teammate"
    if body.actor_user_id:
        actor_user = db.query(User).filter(User.id == body.actor_user_id).first()
        if actor_user:
            actor_name = actor_user.name

    # Broadcast user chat message if team session
    if session.team_id:
        broadcast_to_team(
            team_id=session.team_id,
            message={
                "type": "chat_message",
                "user_id": body.actor_user_id,
                "name": actor_name,
                "message": body.message,
            },
            exclude_user_id=body.actor_user_id,
        )

    # 2. Call Gemini
    reply_text = await chat_with_gemini(
        scenario=challenge.scenario or "",
        current_code=session.current_code,
        message=body.message,
    )

    # 3. Persist assistant message
    assistant_msg = ChatMessage(
        session_id=session_id,
        user_id=None,
        role="assistant",
        content=reply_text,
    )
    db.add(assistant_msg)
    db.commit()

    # Broadcast assistant reply if team session
    if session.team_id:
        broadcast_to_team(
            team_id=session.team_id,
            message={
                "type": "assistant_reply",
                "message": reply_text,
            },
        )

    return {"reply": reply_text}


@router.get("/{session_id}/messages")
def get_messages(session_id: int, db: Session = Depends(get_db)):
    """
    Return all chat messages for a session, ordered by creation time.
    Used by the team workspace to poll for new messages.
    """
    session = db.query(ChallengeSession).filter(ChallengeSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    return [
        {
            "id": msg.id,
            "user_id": msg.user_id,
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }
        for msg in messages
    ]


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

    _authorize_session_actor(session, body.actor_user_id, db)

    session.current_code = body.code
    db.commit()
    return {"saved": True}


@router.post("/{session_id}/submit")
async def submit_session(
    session_id: int,
    body: Optional[SubmitRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Mark the session as submitted, evaluate the code + chat transcript with
    Gemini, store a Submission + Evaluation row, and return submission_id.
    """
    session = db.query(ChallengeSession).filter(ChallengeSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.submitted_at is not None:
        raise HTTPException(status_code=400, detail="Session already submitted")

    actor_id = body.actor_user_id if body else None
    _authorize_session_actor(session, actor_id, db)

    # If team session, check 2-member floor safety net
    team = None
    if session.team_id is not None:
        member_count = (
            db.query(func.count(TeamMember.id))
            .filter(TeamMember.team_id == session.team_id)
            .scalar()
            or 0
        )
        if member_count < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team must have at least 2 members to submit.",
            )
        team = db.query(Team).filter(Team.id == session.team_id).first()

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
    if team:
        team.status = "submitted"
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
    sub_name = team.name if team else session.name
    sub_user_id = None if team else session.user_id
    sub_team_id = team.id if team else None

    submission = Submission(
        name=sub_name,
        user_id=sub_user_id,
        team_id=sub_team_id,
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
