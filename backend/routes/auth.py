import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import bcrypt

from database.connection import get_db
from models.user import User
from schemas.user import UserRegister, UserOut, UserLogin, LoginOut
from services.activity_service import record_visit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["auth"])



def hash_password(password: str) -> str:
    pw_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


@router.post("/register", response_model=UserOut)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# SESSION MODEL TRADEOFF NOTE:
# Authentication in 1Code is client-side via localStorage per session.js, without server-issued
# JWT tokens. Banning an account blocks credential authentication immediately upon next login attempt.
# Existing client-side sessions on already-open tabs will be prevented from authenticating new sessions
# or re-logging in once their browser session resets.


@router.post("/login", response_model=LoginOut)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid Credentials")

    if getattr(user, "is_banned", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been suspended. Contact support if you believe this is a mistake.",
        )

    try:
        record_visit(db, user.id)
    except Exception as e:
        logger.warning(f"Failed to record visit for user {user.id}: {e}")

    return LoginOut(user_id=user.id, name=user.name, is_admin=user.is_admin)


@router.post("/users/admin-login", response_model=LoginOut)
def admin_login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid Credentials")

    if getattr(user, "is_banned", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been suspended. Contact support if you believe this is a mistake.",
        )

    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Access Denied: Admins Only")

    return LoginOut(user_id=user.id, name=user.name, is_admin=user.is_admin)