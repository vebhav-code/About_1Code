import time
from datetime import datetime, timezone
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from database.connection import get_db
from models.site_visit import SiteVisit
from models.user import User

router = APIRouter(prefix="/api/stats", tags=["stats"])

# ---------------------------------------------------------------------------
# Rate Limiting & TTL Cache (In-Process)
# ---------------------------------------------------------------------------
# NOTE: The rate-limiting window map and landing stats cache below are stored in-memory
# within this single process. They reset upon server deploy/restart, which is a simple,
# privacy-friendly, and lightweight tradeoff suitable for landing page stats.
# ---------------------------------------------------------------------------
_visit_rate_limit_map: Dict[str, List[float]] = {}
RATE_LIMIT_WINDOW_SEC = 60.0
RATE_LIMIT_MAX_REQUESTS = 5

_landing_stats_cache: Dict[str, object] = {"timestamp": 0.0, "data": None}
LANDING_STATS_CACHE_TTL = 10.0  # 10 seconds TTL cache


def _check_visit_rate_limit(request: Request):
    client_ip = request.client.host if (request.client and request.client.host) else "127.0.0.1"
    now = time.time()

    timestamps = _visit_rate_limit_map.get(client_ip, [])
    # Keep only timestamps within the last 60 seconds
    timestamps = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW_SEC]

    if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        _visit_rate_limit_map[client_ip] = timestamps
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for visit logging",
        )

    timestamps.append(now)
    _visit_rate_limit_map[client_ip] = timestamps


@router.post("/visit")
def log_visit(request: Request, db: Session = Depends(get_db)):
    """
    Log an anonymous daily site visit increment.
    No user identity, IP address, or PII is recorded in the database.
    Rate limited to 5 pings/minute per IP address.
    """
    _check_visit_rate_limit(request)

    today = datetime.now(timezone.utc).date()

    try:
        if db.bind and db.bind.dialect.name == "postgresql":
            stmt = pg_insert(SiteVisit).values(visit_date=today, count=1)
            stmt = stmt.on_conflict_do_update(
                index_elements=["visit_date"],
                set_={"count": SiteVisit.count + 1},
            )
            db.execute(stmt)
            db.commit()
        else:
            # Fallback for SQLite / generic DBs in testing environments
            visit = db.query(SiteVisit).filter(SiteVisit.visit_date == today).first()
            if visit:
                visit.count += 1
            else:
                visit = SiteVisit(visit_date=today, count=1)
                db.add(visit)
            db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record site visit: {str(e)}",
        )

    return {"ok": True}


@router.get("/landing")
def get_landing_stats(db: Session = Depends(get_db)):
    """
    Public, read-only endpoint returning total registered user count and today's visitor count.
    Cached for 10s to handle high-volume public landing page traffic gracefully.
    """
    now = time.time()
    cached_data = _landing_stats_cache.get("data")
    cached_time = _landing_stats_cache.get("timestamp", 0.0)

    if cached_data is not None and (now - cached_time < LANDING_STATS_CACHE_TTL):
        return cached_data

    today = datetime.now(timezone.utc).date()

    total_users = db.query(func.count(User.id)).scalar() or 0
    today_visit_count = (
        db.query(SiteVisit.count)
        .filter(SiteVisit.visit_date == today)
        .scalar()
        or 0
    )

    result = {
        "total_users": total_users,
        "visitors_today": today_visit_count,
    }

    _landing_stats_cache["timestamp"] = now
    _landing_stats_cache["data"] = result

    return result
