from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import ADMIN_KEY
from database.connection import get_db
from schemas.admin import AdminChallengeCreate, AdminChallengeResponse, AdminChallengeUpdate, AdminChallengeDetailResponse
from services.challenge_upload_service import ChallengeUploadService
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


@router.post("/challenges", response_model=AdminChallengeResponse, status_code=status.HTTP_201_CREATED)
def create_challenge(payload: AdminChallengeCreate, db: Session = Depends(get_db)) -> Dict[str, Any]:
    service = ChallengeUploadService(db)
    return service.create_challenge(payload)


@router.get("/challenges", response_model=list[AdminChallengeResponse])
def list_challenges(db: Session = Depends(get_db)) -> list[Dict[str, Any]]:
    service = ChallengeUploadService(db)
    return service.list_challenges()


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


@router.put("/challenges/{challenge_id}", response_model=AdminChallengeResponse)
def update_challenge(
    challenge_id: int,
    payload: AdminChallengeUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    service = ChallengeUploadService(db)
    return service.update_challenge(challenge_id, payload.model_dump(exclude_unset=True))


@router.delete("/challenges/{challenge_id}", response_model=AdminChallengeResponse)
def delete_challenge(
    challenge_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    service = ChallengeUploadService(db)
    return service.delete_challenge(challenge_id)
