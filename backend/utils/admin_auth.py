from typing import Optional
from fastapi import Header, HTTPException, status
from config import ADMIN_KEY


def require_admin_key(x_admin_key: Optional[str] = Header(None)) -> None:
    if not ADMIN_KEY or not x_admin_key or x_admin_key != ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin key",
        )
