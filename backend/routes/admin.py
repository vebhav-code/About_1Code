from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from config import ADMIN_KEY
from database.connection import get_db
from models.user import User
from models.submission import Submission
from schemas.admin import (
    AdminChallengeCreate,
    AdminChallengeResponse,
    AdminChallengeUpdate,
    AdminChallengeDetailResponse,
    AdminChallengeDeleteResponse,
    AdminUserSummary,
    AdminUserDetailResponse,
    AdminBanRequest,
)
from services.challenge_upload_service import ChallengeUploadService
from services.profile_service import get_user_profile
from utils.admin_auth import require_admin_key

login_router = APIRouter(prefix="/api/admin", tags=["Admin"])

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin_key)],
)


class AdminLoginRequest(BaseModel):
    key: Optional[str] = None
    password: Optional[str] = None


@login_router.post("/login")
def admin_login(body: Optional[AdminLoginRequest] = None):
    try:
        submitted_key = (
            body.key if (body and body.key) else (body.password if (body and body.password) else None)
        )
        if not ADMIN_KEY or submitted_key != ADMIN_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin key",
            )
        return {"valid": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/challenges", response_model=AdminChallengeDetailResponse, status_code=status.HTTP_201_CREATED)
def create_challenge(payload: AdminChallengeCreate, db: Session = Depends(get_db)) -> Dict[str, Any]:
    service = ChallengeUploadService(db)
    return service.create_challenge(payload)


@router.get("/challenges", response_model=list[AdminChallengeResponse])
def list_challenges(
    include_archived: bool = Query(False),
    db: Session = Depends(get_db)
) -> list[Dict[str, Any]]:
    service = ChallengeUploadService(db)
    return service.list_challenges(include_archived=include_archived)


@router.get("/challenges/{challenge_id}", response_model=AdminChallengeDetailResponse)
def get_challenge(
    challenge_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    service = ChallengeUploadService(db)
    challenge = service.get_challenge(challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")
    return challenge


@router.put("/challenges/{challenge_id}", response_model=AdminChallengeDetailResponse)
def update_challenge(
    challenge_id: int,
    payload: AdminChallengeUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:

    service = ChallengeUploadService(db)
    return service.update_challenge(challenge_id, payload.model_dump(exclude_unset=True))


@router.delete("/challenges/{challenge_id}", response_model=AdminChallengeDeleteResponse)
def delete_challenge(
    challenge_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    service = ChallengeUploadService(db)
    return service.delete_challenge(challenge_id)


# ---------------------------------------------------------------------------
# Admin User Management Routes
# ---------------------------------------------------------------------------

@router.get("/users", response_model=List[AdminUserSummary])
def list_users(
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> List[AdminUserSummary]:
    query = db.query(User)
    if q and q.strip():
        search_pattern = f"%{q.strip()}%"
        query = query.filter((User.name.ilike(search_pattern)) | (User.email.ilike(search_pattern)))

    users = query.order_by(User.id.asc()).all()

    summaries = []
    for u in users:
        total_attempted = (
            db.query(func.count(Submission.id))
            .filter(Submission.user_id == u.id)
            .scalar()
            or 0
        )
        total_completed = total_attempted  # Submissions represent completed attempts in 1Code

        summaries.append(
            AdminUserSummary(
                id=u.id,
                name=u.name,
                email=u.email,
                is_admin=u.is_admin if u.is_admin is not None else False,
                is_banned=u.is_banned if hasattr(u, "is_banned") and u.is_banned is not None else False,
                banned_reason=getattr(u, "banned_reason", None),
                banned_at=getattr(u, "banned_at", None),
                created_at=u.created_at or datetime.now(timezone.utc),
                total_attempted=total_attempted,
                total_completed=total_completed,
            )
        )

    return summaries


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
def get_user_detail(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    profile_dict = get_user_profile(user_id, db)
    if profile_dict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")

    profile_dict["email"] = user.email
    profile_dict["is_admin"] = user.is_admin if user.is_admin is not None else False
    profile_dict["is_banned"] = getattr(user, "is_banned", False) or False
    profile_dict["banned_reason"] = getattr(user, "banned_reason", None)
    profile_dict["banned_at"] = getattr(user, "banned_at", None)

    return AdminUserDetailResponse(**profile_dict)


@router.post("/users/{user_id}/ban", response_model=AdminUserSummary)
def ban_user(
    user_id: int,
    body: Optional[AdminBanRequest] = None,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # RESTRICTION: Admins cannot ban other admin accounts to prevent accidental admin lockout.
    if user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin users cannot be banned via the admin console.",
        )

    reason = body.reason.strip() if (body and body.reason and body.reason.strip()) else "Suspended by administrator."

    user.is_banned = True
    user.banned_reason = reason
    user.banned_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    total_attempted = (
        db.query(func.count(Submission.id))
        .filter(Submission.user_id == user.id)
        .scalar()
        or 0
    )

    return AdminUserSummary(
        id=user.id,
        name=user.name,
        email=user.email,
        is_admin=user.is_admin or False,
        is_banned=True,
        banned_reason=user.banned_reason,
        banned_at=user.banned_at,
        created_at=user.created_at or datetime.now(timezone.utc),
        total_attempted=total_attempted,
        total_completed=total_attempted,
    )


@router.post("/users/{user_id}/unban", response_model=AdminUserSummary)
def unban_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_banned = False
    user.banned_reason = None
    user.banned_at = None
    db.commit()
    db.refresh(user)

    total_attempted = (
        db.query(func.count(Submission.id))
        .filter(Submission.user_id == user.id)
        .scalar()
        or 0
    )

    return AdminUserSummary(
        id=user.id,
        name=user.name,
        email=user.email,
        is_admin=user.is_admin or False,
        is_banned=False,
        banned_reason=None,
        banned_at=None,
        created_at=user.created_at or datetime.now(timezone.utc),
        total_attempted=total_attempted,
        total_completed=total_attempted,
    )
