"""
routes/session.py
Session-based challenge workspace routes for Approach Mode.
Replaces code execution with free-text approach architecture writing and AI evaluation.
Generalised for both individual and team mode sessions.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict

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
from services.activity_service import record_visit
from services.gemini_service import (
    chat_with_gemini,
    evaluate_submission_with_gemini,
    _parse_constraints_list,
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


class SaveApproachRequest(BaseModel):
    approach: Optional[str] = None
    code: Optional[str] = None  # Backward-compatibility fallback alias
    actor_user_id: Optional[int] = None


class SubmitRequest(BaseModel):
    actor_user_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Authorization Helper
# ---------------------------------------------------------------------------

def _authorize_session_actor(
    session: ChallengeSession,
    user_id: Optional[int],
    db: Session,
    require_leader: bool = False
) -> None:
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

        if require_leader:
            team = db.query(Team).filter(Team.id == session.team_id).first()
            if not team or user_id != team.leader_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the team leader can submit this challenge for grading.",
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
    Create a new individual ChallengeSession row for Approach Mode.
    Returns session_id + challenge metadata including constraints list.
    """
    user = db.query(User).filter(User.id == body.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found — please log in again.",
        )

    challenge = db.query(Challenge).filter(Challenge.id == body.challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    if challenge.mode == "team":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This challenge is team-only. Join or create a team to attempt it.",
        )

    # 1. Check existing submission
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

    # 2. Check team membership
    active_member = (
        db.query(TeamMember)
        .join(Team, TeamMember.team_id == Team.id)
        .filter(
            TeamMember.user_id == body.user_id,
            Team.challenge_id == body.challenge_id,
            Team.status.in_(["forming", "active"]),
        )
        .first()
    )
    if active_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already part of an active or forming team for this challenge.",
        )

    constraints_list = _parse_constraints_list(challenge.constraints)

    # 3. Resume existing open individual session if one exists
    existing_open_session = (
        db.query(ChallengeSession)
        .filter(
            ChallengeSession.challenge_id == body.challenge_id,
            ChallengeSession.user_id == body.user_id,
            ChallengeSession.submitted_at.is_(None),
        )
        .first()
    )
    if existing_open_session:
        return {
            "session_id": existing_open_session.id,
            "starter_code": existing_open_session.current_approach,
            "current_approach": existing_open_session.current_approach,
            "challenge": {
                "title": challenge.title,
                "scenario": challenge.scenario,
                "time_limit": challenge.time_limit,
                "constraints": constraints_list,
            },
        }

    starter_approach = load_starter_code(challenge)

    session = ChallengeSession(
        challenge_id=challenge.id,
        user_id=body.user_id,
        team_id=None,
        name=body.name.strip() or "Anonymous",
        hypothesis=body.hypothesis.strip(),
        current_approach=starter_approach,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    try:
        record_visit(db, body.user_id)
    except Exception as e:
        logger.warning(f"Failed to record visit on session start for user {body.user_id}: {e}")

    return {
        "session_id": session.id,
        "starter_code": starter_approach,
        "current_approach": starter_approach,
        "challenge": {
            "title": challenge.title,
            "scenario": challenge.scenario,
            "time_limit": challenge.time_limit,
            "constraints": constraints_list,
        },
    }


@router.post("/{session_id}/chat")
async def send_message(
    session_id: int,
    body: ChatRequest,
    db: Session = Depends(get_db),
):
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

    actor_name = "Teammate"
    if body.actor_user_id:
        actor_user = db.query(User).filter(User.id == body.actor_user_id).first()
        if actor_user:
            actor_name = actor_user.name

    if session.team_id:
        await broadcast_to_team(
            team_id=session.team_id,
            message={
                "type": "chat_message",
                "user_id": body.actor_user_id,
                "name": actor_name,
                "message": body.message,
            },
            exclude_user_id=body.actor_user_id,
        )

    # 2. Call Gemini sounding-board with actor's prior history & challenge constraints
    prior_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id, ChatMessage.user_id == body.actor_user_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in prior_messages if m.id != user_msg.id]

    constraints_list = _parse_constraints_list(challenge.constraints if challenge else None)

    reply_text = await chat_with_gemini(
        scenario=challenge.scenario or "" if challenge else "",
        current_approach=session.current_approach,
        message=body.message,
        constraints=constraints_list,
        history=history,
    )

    # 3. Persist assistant message
    assistant_msg = ChatMessage(
        session_id=session_id,
        user_id=body.actor_user_id,
        role="assistant",
        content=reply_text,
    )
    db.add(assistant_msg)
    db.commit()

    if session.team_id:
        await broadcast_to_team(
            team_id=session.team_id,
            message={
                "type": "assistant_reply",
                "message": reply_text,
                "msg_id": assistant_msg.id,
                "user_id": body.actor_user_id,
            },
        )

    return {"reply": reply_text}


@router.get("/{session_id}")
def get_session_details(session_id: int, db: Session = Depends(get_db)):
    session = db.query(ChallengeSession).filter(ChallengeSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    challenge = db.query(Challenge).filter(Challenge.id == session.challenge_id).first()
    constraints_list = _parse_constraints_list(challenge.constraints if challenge else None)

    return {
        "id": session.id,
        "challenge_id": session.challenge_id,
        "team_id": session.team_id,
        "current_approach": session.current_approach,
        "current_code": session.current_approach,  # Backward-compatibility alias
        "submitted_at": session.submitted_at.isoformat() if session.submitted_at else None,
        "challenge": {
            "title": challenge.title if challenge else "",
            "slug": challenge.slug if challenge else "",
            "scenario": challenge.scenario if challenge else "",
            "time_limit": challenge.time_limit if challenge else 45,
            "mode": challenge.mode if challenge else "individual",
            "constraints": constraints_list,
        } if challenge else None,
    }


@router.get("/{session_id}/messages")
def get_messages(session_id: int, db: Session = Depends(get_db)):
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
async def save_code(
    session_id: int,
    body: SaveApproachRequest,
    db: Session = Depends(get_db),
):
    """Update ChallengeSession.current_approach. Called from the approach editor."""
    session = db.query(ChallengeSession).filter(ChallengeSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.submitted_at is not None:
        raise HTTPException(status_code=400, detail="Session already submitted")

    _authorize_session_actor(session, body.actor_user_id, db)

    approach_text = body.approach if body.approach is not None else body.code
    if approach_text is not None:
        session.current_approach = approach_text

    db.commit()

    if session.team_id:
        await broadcast_to_team(
            team_id=session.team_id,
            message={
                "type": "approach_update",
                "current_approach": session.current_approach,
                "user_id": body.actor_user_id,
            },
            exclude_user_id=body.actor_user_id,
        )

    return {"saved": True}


@router.post("/{session_id}/submit")
async def submit_session(
    session_id: int,
    body: Optional[SubmitRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Mark the session as submitted, evaluate the approach write-up with Gemini,
    store a Submission + Evaluation row, and return submission_id.
    """
    session = db.query(ChallengeSession).filter(ChallengeSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.submitted_at is not None:
        raise HTTPException(status_code=400, detail="Session already submitted")

    actor_id = body.actor_user_id if body else None
    _authorize_session_actor(session, actor_id, db, require_leader=True)

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

    # 1. Compute lateness
    started_at = session.started_at
    if started_at:
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        elapsed_minutes = (datetime.now(timezone.utc) - started_at).total_seconds() / 60
    else:
        elapsed_minutes = 0.0

    time_limit = challenge.time_limit or 45
    is_late = elapsed_minutes > time_limit

    # 2. Mark session submitted
    session.submitted_at = datetime.now(timezone.utc)
    if team:
        team.status = "submitted"
    db.flush()

    # 3. Assemble chat transcript & official reference solution notes
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

    official_solution_notes = challenge.official_solution or "No reference notes available for this challenge."

    # 4. Run Gemini evaluation directly on submitted approach text
    try:
        gemini_result = await evaluate_submission_with_gemini(
            approach_text=session.current_approach or "(no approach written)",
            challenge=challenge,
            chat_transcript=chat_transcript,
            official_solution_content=official_solution_notes,
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
        topic_knowledge_score=gemini_result.get("topic_knowledge", 0),
        prompt_quality_score=gemini_result.get("prompt_quality", 0),
        open_source_usage_score=gemini_result.get("open_source_usage", 0),
        optimization_score=gemini_result.get("optimization", 0),
        overall_score=gemini_result.get("total_score", 0),
        approach_text=session.current_approach or "",
        feedback=gemini_result.get("overall_feedback", ""),
    )
    db.add(submission)
    db.flush()

    # 6. Store Evaluation
    evaluation = Evaluation(
        submission_id=submission.id,
        hypothesis=gemini_result.get("hypothesis", 0),
        prompt_quality=gemini_result.get("prompt_quality", 0),
        open_source_usage=gemini_result.get("open_source_usage", 0),
        optimization=gemini_result.get("optimization", 0),
        topic_knowledge=gemini_result.get("topic_knowledge", 0),
        total_score=gemini_result.get("total_score", 0),
        strengths=gemini_result.get("strengths", []),
        improvements=gemini_result.get("improvements", []),
        overall_feedback=gemini_result.get("overall_feedback", ""),
    )
    db.add(evaluation)
    db.commit()

    if team:
        await broadcast_to_team(
            team_id=team.id,
            message={
                "type": "team_submitted",
                "submission_id": submission.id,
            },
        )

    return {
        "passed": True,
        "submission_id": submission.id,
    }
