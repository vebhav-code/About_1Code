import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from database.connection import get_db
from models.user import User
from schemas.user import ProfileUpdate
from services.profile_service import get_user_profile
from utils.file_validation import validate_avatar_file, FileValidationError

router = APIRouter(prefix="/api/users", tags=["profile"])

UPLOADS_ROOT = Path(__file__).resolve().parent.parent / "uploads" / "avatars"


@router.get("/{user_id}/profile")
def get_profile(user_id: int, db: Session = Depends(get_db)):
    profile = get_user_profile(db, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    return profile


@router.patch("/{user_id}/profile")
@router.put("/{user_id}/profile")
def update_profile(user_id: int, payload: ProfileUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        if payload.bio is not None:
            user.bio = payload.bio
        if payload.avatar_url is not None:
            user.avatar_url = payload.avatar_url
        if payload.github_url is not None:
            user.github_url = str(payload.github_url)
        if payload.linkedin_url is not None:
            user.linkedin_url = str(payload.linkedin_url)
        if payload.website_url is not None:
            user.website_url = str(payload.website_url)

        db.commit()
        db.refresh(user)
        return get_user_profile(db, user_id)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update profile: {str(e)}"
        )


@router.post("/{user_id}/avatar")
async def upload_avatar(user_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    contents = await file.read()
    try:
        validate_avatar_file(
            filename=file.filename,
            content_type=file.content_type,
            file_size=len(contents),
        )
    except FileValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user_dir = UPLOADS_ROOT / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ".png"
    unique_filename = f"avatar_{uuid.uuid4().hex[:8]}{ext}"
    target_path = user_dir / unique_filename
    target_path.write_bytes(contents)

    avatar_url = f"/uploads/avatars/{user_id}/{unique_filename}"
    user.avatar_url = avatar_url
    db.commit()
    db.refresh(user)

    return get_user_profile(db, user_id)
