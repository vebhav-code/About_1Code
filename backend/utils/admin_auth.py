from fastapi import Header, HTTPException, status
from config import ADMIN_KEY


def require_admin_key(x_admin_key: str = Header(...)) -> None:
    if not ADMIN_KEY or x_admin_key != ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key",
        )
