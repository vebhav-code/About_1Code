"""
routes/session.py
Session-based challenge workspace routes.
Replaces the zip-upload flow with a server-tracked session + live editor + chat.
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
from models.submission_file import SubmissionFile
from models.team import Team
from models.team_member import TeamMember
from models.user import User
from routes.team_ws import broadcast_to_team
from services.activity_service import record_visit
from services.execution_service import run_submission_code
from services.gemini_service import (
    chat_with_gemini,
    check_code_for_errors,
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
    code: Optional[str] = None
    filename: Optional[str] = None
    files: Optional[Dict[str, str]] = None
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
    """
    Ensure the actor is authorized to interact with the session.
    If individual session: user_id can match or be unenforced for backward compatibility.
    If team session: actor_user_id MUST be provided and MUST be a member of the team.
    If require_leader is True: actor_user_id MUST be the team leader.
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

    # 1. Check if user is in an active or forming team for this challenge
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

    # 2. Check if user already submitted this challenge (individually or via team)
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

    # 3. Resume existing open/unsubmitted individual session if one exists
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
            "starter_code": existing_open_session.current_code,
            "challenge": {
                "title": challenge.title,
                "scenario": challenge.scenario,
                "time_limit": challenge.time_limit,
            },
        }

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

    try:
        record_visit(db, body.user_id)
    except Exception as e:
        logger.warning(f"Failed to record visit on session start for user {body.user_id}: {e}")

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

    # 2. Call Gemini with actor's prior conversation history
    prior_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id, ChatMessage.user_id == body.actor_user_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in prior_messages if m.id != user_msg.id]

    reply_text = await chat_with_gemini(
        scenario=challenge.scenario or "",
        current_code=session.current_code,
        message=body.message,
        history=history,
    )

    # 3. Persist assistant message (attributed to the requesting user)
    assistant_msg = ChatMessage(
        session_id=session_id,
        user_id=body.actor_user_id,
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
                "msg_id": assistant_msg.id,
                "user_id": body.actor_user_id,
            },
        )

    return {"reply": reply_text}


@router.get("/{session_id}")
def get_session_details(session_id: int, db: Session = Depends(get_db)):
    """
    Return session state including current_code, files, challenge metadata, and time_limit.
    Used when a user or teammate reloads/opens the workspace.
    """
    session = db.query(ChallengeSession).filter(ChallengeSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    challenge = db.query(Challenge).filter(Challenge.id == session.challenge_id).first()

    return {
        "id": session.id,
        "challenge_id": session.challenge_id,
        "team_id": session.team_id,
        "current_code": session.current_code,
        "submitted_at": session.submitted_at.isoformat() if session.submitted_at else None,
        "challenge": {
            "title": challenge.title if challenge else "",
            "slug": challenge.slug if challenge else "",
            "scenario": challenge.scenario if challenge else "",
            "time_limit": challenge.time_limit if challenge else 45,
            "mode": challenge.mode if challenge else "individual",
        } if challenge else None,
    }


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

    if body.files is not None:
        session.current_code = json.dumps(body.files)
    elif body.filename and body.code is not None:
        try:
            files_dict = json.loads(session.current_code or "{}")
            if not isinstance(files_dict, dict):
                files_dict = {}
        except Exception:
            files_dict = {}
        files_dict[body.filename] = body.code
        session.current_code = json.dumps(files_dict)
    elif body.code is not None:
        session.current_code = body.code

    db.commit()

    if session.team_id:
        broadcast_to_team(
            team_id=session.team_id,
            message={
                "type": "code_update",
                "current_code": session.current_code,
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
    Mark the session as submitted, evaluate the code + chat transcript with
    Gemini, store a Submission + Evaluation row, and return submission_id.
    """
    session = db.query(ChallengeSession).filter(ChallengeSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.submitted_at is not None:
        raise HTTPException(status_code=400, detail="Session already submitted")

    actor_id = body.actor_user_id if body else None
    _authorize_session_actor(session, actor_id, db, require_leader=True)

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

    # 1. Gather all submission files
    files_dict = {}
    if session.current_code:
        try:
            parsed = json.loads(session.current_code)
            if isinstance(parsed, dict):
                files_dict = parsed
        except Exception:
            pass

    if not files_dict:
        if challenge.files:
            files_dict = {f.filename: f.starter_content for f in challenge.files}
        else:
            files_dict = {"main.py": session.current_code or ""}

    # 2. Run isolated execution check as scoring gate
    exec_result = run_submission_code(
        files=files_dict,
        run_command=getattr(challenge, "run_command", None) or "pytest",
        timeout_seconds=15,
    )

    # Legacy single-file mode fallback: if no ChallengeFile records exist and pytest returns 5 (no tests found), treat as passed
    if not exec_result["passed"] and exec_result["exit_code"] == 5 and not getattr(challenge, "files", None):
        exec_result["passed"] = True

    # 3. Store execution log file

    log_dir = Path(__file__).resolve().parent.parent / "uploads" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_filename = f"sub_exec_{session_id}_{timestamp_str}.log"
    log_file_path = log_dir / log_filename

    log_body = (
        f"=== 1CODE SUBMISSION EXECUTION LOG ===\n"
        f"Session ID: {session_id}\n"
        f"Challenge: {challenge.title} ({challenge.slug})\n"
        f"Command: {challenge.run_command or 'pytest'}\n"
        f"Passed: {exec_result['passed']}\n"
        f"Exit Code: {exec_result['exit_code']}\n"
        f"Duration: {exec_result['duration_ms']} ms\n\n"
        f"--- STDOUT ---\n{exec_result['stdout']}\n\n"
        f"--- STDERR ---\n{exec_result['stderr']}\n"
    )
    log_file_path.write_text(log_body, encoding="utf-8")
    relative_log_path = f"uploads/logs/{log_filename}"

    # 4. If execution failed, DO NOT proceed to Gemini evaluation or create scored submission
    if not exec_result["passed"]:
        db.rollback()
        return {
            "passed": False,
            "exit_code": exec_result["exit_code"],
            "stdout": exec_result["stdout"],
            "stderr": exec_result["stderr"],
            "duration_ms": exec_result["duration_ms"],
            "debug_log_path": relative_log_path,
            "detail": "Execution failed. All project tests must pass before submission can be evaluated by AI.",
        }

    # 5. Mark session submitted
    session.submitted_at = datetime.now(timezone.utc)
    if team:
        team.status = "submitted"
    db.flush()

    # 6. Assemble chat transcript & official solution
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

    try:
        official_solution = read_official_solution(challenge)
    except Exception:
        official_solution = "No official solution reference is available for this challenge."

    # 7. Ground Gemini evaluation with code & execution output
    full_user_code_with_exec = (
        f"{session.current_code or '(no code submitted)'}\n\n"
        f"--- REAL EXECUTION RUN RESULTS ---\n"
        f"Exit Code: {exec_result['exit_code']}\n"
        f"Stdout:\n{exec_result['stdout']}\n"
        f"Stderr:\n{exec_result['stderr']}\n"
    )

    try:
        gemini_result = await evaluate_submission_with_gemini(
            submission=None,
            challenge=challenge,
            db_log_content=chat_transcript,
            user_code_content=full_user_code_with_exec,
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

    # 8. Store Submission
    sub_name = team.name if team else session.name
    sub_user_id = None if team else session.user_id
    sub_team_id = team.id if team else None

    submission = Submission(
        name=sub_name,
        user_id=sub_user_id,
        team_id=sub_team_id,
        challenge_id=challenge.id,
        fixed_project_path=None,
        debug_log_path=relative_log_path,
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

    # 9. Store SubmissionFile rows
    for filename, content in files_dict.items():
        db.add(
            SubmissionFile(
                submission_id=submission.id,
                filename=filename,
                content=content or "",
            )
        )

    # 10. Store Evaluation
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

    if team:
        broadcast_to_team(
            team_id=team.id,
            message={
                "type": "team_submitted",
                "submission_id": submission.id,
            },
        )

    return {
        "passed": True,
        "submission_id": submission.id,
        "stdout": exec_result["stdout"],
        "stderr": exec_result["stderr"],
    }


@router.post("/{session_id}/check-code")
async def check_code(session_id: int, db: Session = Depends(get_db)):
    session = db.query(ChallengeSession).filter(ChallengeSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    challenge = db.query(Challenge).filter(Challenge.id == session.challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    files = {}
    if session.current_code:
        try:
            parsed = json.loads(session.current_code)
            if isinstance(parsed, dict):
                files = parsed
            else:
                files = {"main.py": str(session.current_code)}
        except Exception:
            files = {"main.py": str(session.current_code)}

    if not files:
        if getattr(challenge, "files", None):
            files = {f.filename: f.starter_content for f in challenge.files}
        else:
            files = {"main.py": session.current_code or ""}

    run_cmd = getattr(challenge, "run_command", None) or "python main.py"
    result = run_submission_code(
        files=files,
        run_command=run_cmd,
        timeout_seconds=15,
    )
    return {
        "passed": result["passed"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "exit_code": result.get("exit_code"),
    }


