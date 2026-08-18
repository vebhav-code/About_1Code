"""
routes/team.py
Team creation, joining, listing, roster management, and team session start endpoints.
"""

import logging
import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.connection import get_db
from models.challenge import Challenge
from models.session import ChallengeSession
from models.submission import Submission
from models.team import Team
from models.team_member import TeamMember
from models.team_join_request import TeamJoinRequest
from models.user import User
from routes.team_ws import broadcast_to_team
from schemas.team import (
    TeamCreate,
    TeamJoin,
    TeamMemberOut,
    TeamResponse,
    TeamSummary,
)
from services.session_helpers import load_starter_code

router = APIRouter(prefix="/api", tags=["teams"])
logger = logging.getLogger(__name__)


class TeamStartRequest(BaseModel):
    user_id: int


def _generate_invite_code(db: Session, length: int = 8) -> str:
    """Generate a unique random alphanumeric invite code."""
    for _ in range(10):
        code = secrets.token_urlsafe(length)[:length].upper()
        existing = db.query(Team).filter(Team.invite_code == code).first()
        if not existing:
            return code
    return secrets.token_urlsafe(12).upper()


def _check_user_existing_participation(user_id: int, challenge_id: int, db: Session) -> None:
    """
    Application-level safeguard:
    Prevents a user from creating or joining a second 'forming' or 'active' team
    or submitting for the same challenge_id.
    
    Note: Since team_members does not directly contain challenge_id, this check is
    enforced cleanly at the service/route level via a SQL JOIN between TeamMember and Team.
    """
    # 1. Check direct individual submission
    existing_sub = (
        db.query(Submission)
        .filter(Submission.user_id == user_id, Submission.challenge_id == challenge_id)
        .first()
    )
    if existing_sub:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You've already submitted this challenge. Each challenge can only be attempted once.",
        )

    # 2. Check team submission
    existing_team_sub = (
        db.query(Submission)
        .join(Team, Submission.team_id == Team.id)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .filter(TeamMember.user_id == user_id, Submission.challenge_id == challenge_id)
        .first()
    )
    if existing_team_sub:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Your team has already submitted this challenge.",
        )

    # 3. Check active or forming team membership for this challenge
    active_member = (
        db.query(TeamMember)
        .join(Team, TeamMember.team_id == Team.id)
        .filter(
            TeamMember.user_id == user_id,
            Team.challenge_id == challenge_id,
            Team.status.in_(["forming", "active"]),
        )
        .first()
    )
    if active_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already part of an active or forming team for this challenge.",
        )


def _build_team_response(team: Team, challenge_team_size: int, db: Session) -> TeamResponse:
    members = (
        db.query(TeamMember, User.name)
        .join(User, TeamMember.user_id == User.id)
        .filter(TeamMember.team_id == team.id)
        .all()
    )
    member_list = [
        TeamMemberOut(user_id=m.user_id, name=name or "Anonymous")
        for m, name in members
    ]
    return TeamResponse(
        id=team.id,
        challenge_id=team.challenge_id,
        name=team.name,
        invite_code=team.invite_code,
        leader_user_id=team.leader_user_id,
        status=team.status,
        team_size=challenge_team_size,
        members=member_list,
    )


@router.post("/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(body: TeamCreate, db: Session = Depends(get_db)):
    """
    Create a new team for a challenge.
    Rejects if challenge mode is not 'team', or if user is already in a team/submitted.
    """
    challenge = db.query(Challenge).filter(Challenge.id == body.challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    if getattr(challenge, "mode", "individual") != "team":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This challenge is not configured for team mode.",
        )

    user = db.query(User).filter(User.id == body.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")

    _check_user_existing_participation(body.user_id, body.challenge_id, db)

    code = _generate_invite_code(db)
    team = Team(
        challenge_id=body.challenge_id,
        name=body.team_name,
        invite_code=code,
        leader_user_id=body.user_id,
        status="forming",
    )
    db.add(team)
    db.commit()
    db.refresh(team)

    member = TeamMember(team_id=team.id, user_id=body.user_id)
    db.add(member)
    db.commit()

    return _build_team_response(team, challenge.team_size, db)


@router.get("/challenge/{slug}/teams", response_model=List[TeamSummary])
def list_open_teams(
    slug: str,
    user_id: Optional[int] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List open teams ('forming' status and member_count < team_size) for a challenge slug.
    When user_id is provided, teams where that user is already a member are excluded.
    When q is provided, filters teams by case-insensitive partial match on team name.
    """
    challenge = db.query(Challenge).filter(Challenge.slug == slug).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    team_query = db.query(Team).filter(Team.challenge_id == challenge.id, Team.status == "forming")
    if user_id is not None:
        member_team_ids_subquery = (
            db.query(TeamMember.team_id)
            .filter(TeamMember.user_id == user_id)
            .subquery()
        )
        team_query = team_query.filter(~Team.id.in_(member_team_ids_subquery))

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        team_query = team_query.filter(Team.name.ilike(search_term))

    teams = team_query.all()

    summaries = []
    for t in teams:
        member_count = (
            db.query(func.count(TeamMember.id))
            .filter(TeamMember.team_id == t.id)
            .scalar()
            or 0
        )
        if member_count < challenge.team_size:
            leader = db.query(User).filter(User.id == t.leader_user_id).first()
            summaries.append(
                TeamSummary(
                    id=t.id,
                    name=t.name,
                    leader_name=leader.name if leader else "Unknown",
                    member_count=member_count,
                    team_size=challenge.team_size,
                )
            )
    return summaries


@router.post("/teams/join", response_model=TeamResponse)
async def join_team(body: TeamJoin, db: Session = Depends(get_db)):
    """
    Join an existing open team via team_id or invite_code.
    """
    user = db.query(User).filter(User.id == body.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")

    team = None
    if body.team_id is not None:
        team = db.query(Team).filter(Team.id == body.team_id).first()
    elif body.invite_code is not None:
        team = db.query(Team).filter(Team.invite_code == body.invite_code).first()

    if not team:
        raise HTTPException(status_code=404, detail="Team not found.")

    challenge = db.query(Challenge).filter(Challenge.id == team.challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Associated challenge not found.")

    if team.status != "forming":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team has already started or finished.",
        )

    member_count = (
        db.query(func.count(TeamMember.id))
        .filter(TeamMember.team_id == team.id)
        .scalar()
        or 0
    )
    if member_count >= challenge.team_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team is full.",
        )

    # Check if already in this team
    already_member = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team.id, TeamMember.user_id == body.user_id)
        .first()
    )
    if already_member:
        return _build_team_response(team, challenge.team_size, db)

    _check_user_existing_participation(body.user_id, team.challenge_id, db)

    new_member = TeamMember(team_id=team.id, user_id=body.user_id)
    db.add(new_member)
    db.commit()

    # Broadcast member_joined to websocket channel
    await broadcast_to_team(
        team_id=team.id,
        message={
            "type": "member_joined",
            "user_id": user.id,
            "name": user.name,
        },
    )

    return _build_team_response(team, challenge.team_size, db)


@router.get("/teams/{team_id}", response_model=TeamResponse)
def get_team(team_id: int, db: Session = Depends(get_db)):
    """Fetch roster and team info for team_id."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    challenge = db.query(Challenge).filter(Challenge.id == team.challenge_id).first()
    team_size = challenge.team_size if challenge else 4

    return _build_team_response(team, team_size, db)


@router.post("/teams/{team_id}/start")
async def start_team_challenge(team_id: int, body: TeamStartRequest, db: Session = Depends(get_db)):
    """
    Start the shared team session (leader only, requires 2+ members).
    """
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    if body.user_id != team.leader_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the team leader can start the challenge.",
        )

    if team.status != "forming":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team has already started or finished.",
        )

    member_count = (
        db.query(func.count(TeamMember.id))
        .filter(TeamMember.team_id == team.id)
        .scalar()
        or 0
    )
    if member_count < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Need at least 2 members to start.",
        )

    challenge = db.query(Challenge).filter(Challenge.id == team.challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    existing_submission = (
        db.query(Submission)
        .filter(Submission.team_id == team.id, Submission.challenge_id == challenge.id)
        .first()
    )
    if existing_submission:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This team has already submitted this challenge.",
        )

    member_user_ids = [m.user_id for m in db.query(TeamMember).filter(TeamMember.team_id == team.id).all()]
    existing_individual = (
        db.query(Submission)
        .filter(Submission.challenge_id == challenge.id, Submission.user_id.in_(member_user_ids))
        .first()
    )
    if existing_individual:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="One or more team members has already submitted this challenge individually.",
        )

    starter_code = load_starter_code(challenge)

    session = ChallengeSession(
        challenge_id=challenge.id,
        team_id=team.id,
        user_id=None,
        name=team.name,
        hypothesis="Team Challenge Session",
        current_approach=starter_code,
    )
    db.add(session)
    team.status = "active"
    db.commit()
    db.refresh(session)

    challenge_info = {
        "title": challenge.title,
        "scenario": challenge.scenario,
        "time_limit": challenge.time_limit,
    }

    # Broadcast team_started to websocket channel
    await broadcast_to_team(
        team_id=team.id,
        message={
            "type": "team_started",
            "session_id": session.id,
            "starter_code": starter_code,
            "challenge": challenge_info,
        },
    )

    return {
        "session_id": session.id,
        "starter_code": starter_code,
        "challenge": challenge_info,
    }


@router.get("/users/search")
@router.get("/team/users/search")
def search_users(q: str, current_user_id: int, db: Session = Depends(get_db)):
    if len(q.strip()) < 2:
        return []
    results = (
        db.query(User)
        .filter(User.id != current_user_id, User.name.ilike(f"%{q.strip()}%"))
        .limit(10)
        .all()
    )
    return [{"id": u.id, "name": u.name} for u in results]


@router.post("/teams/{team_id}/invite")
@router.post("/team/teams/{team_id}/invite")
def invite_to_team(team_id: int, invited_user_id: int, inviter_user_id: int, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if team.leader_user_id != inviter_user_id:
        raise HTTPException(status_code=403, detail="Only the team leader can send invites")

    challenge = db.query(Challenge).filter(Challenge.id == team.challenge_id).first()
    max_team_size = challenge.team_size if challenge else getattr(team, "team_size", 4)

    current_size = db.query(TeamMember).filter(TeamMember.team_id == team_id).count()
    if current_size >= max_team_size:
        raise HTTPException(status_code=400, detail="Team is already full")

    already_member = db.query(TeamMember).filter(TeamMember.team_id == team_id, TeamMember.user_id == invited_user_id).first()
    if already_member:
        raise HTTPException(status_code=400, detail="User is already on this team")

    existing_request = db.query(TeamJoinRequest).filter(
        TeamJoinRequest.team_id == team_id,
        TeamJoinRequest.invited_user_id == invited_user_id,
        TeamJoinRequest.status == "pending",
    ).first()
    if existing_request:
        raise HTTPException(status_code=400, detail="Invite already pending for this user")

    invite = TeamJoinRequest(team_id=team_id, invited_user_id=invited_user_id, invited_by_user_id=inviter_user_id)
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return {"invite_id": invite.id, "status": "pending"}


@router.get("/users/{user_id}/join-requests")
@router.get("/team/users/{user_id}/join-requests")
def get_pending_requests(user_id: int, db: Session = Depends(get_db)):
    requests = db.query(TeamJoinRequest).filter(
        TeamJoinRequest.invited_user_id == user_id, TeamJoinRequest.status == "pending"
    ).all()
    result = []
    for r in requests:
        team = db.query(Team).filter(Team.id == r.team_id).first()
        inviter = db.query(User).filter(User.id == r.invited_by_user_id).first()
        result.append({
            "request_id": r.id,
            "team_id": r.team_id,
            "team_name": team.name if team else "Unknown Team",
            "invited_by": inviter.name if inviter else "Someone",
        })
    return result


@router.post("/join-requests/{request_id}/respond")
@router.post("/team/join-requests/{request_id}/respond")
async def respond_to_request(request_id: int, accept: bool, responding_user_id: int, db: Session = Depends(get_db)):
    req = db.query(TeamJoinRequest).filter(TeamJoinRequest.id == request_id).first()
    if not req or req.invited_user_id != responding_user_id:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Request already responded to")

    req.status = "accepted" if accept else "declined"
    if accept:
        already = db.query(TeamMember).filter(TeamMember.team_id == req.team_id, TeamMember.user_id == responding_user_id).first()
        if not already:
            db.add(TeamMember(team_id=req.team_id, user_id=responding_user_id))
        db.commit()

        user = db.query(User).filter(User.id == responding_user_id).first()
        user_name = user.name if user else "Anonymous"

        await broadcast_to_team(
            team_id=req.team_id,
            message={
                "type": "member_joined",
                "user_id": responding_user_id,
                "name": user_name,
            },
        )

        team = db.query(Team).filter(Team.id == req.team_id).first()
        challenge_slug = ""
        if team:
            challenge = db.query(Challenge).filter(Challenge.id == team.challenge_id).first()
            if challenge:
                challenge_slug = challenge.slug

        return {
            "status": req.status,
            "team_id": req.team_id,
            "challenge_slug": challenge_slug,
        }

    db.commit()
    return {"status": req.status}

