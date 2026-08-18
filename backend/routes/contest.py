from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database.connection import get_db
from models.challenge import Challenge
from schemas.challenge import ChallengeResponse

from config import TURN_URL, TURN_USERNAME, TURN_CREDENTIAL

router = APIRouter()

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


@router.get("/api/rtc-config")
def get_rtc_config():
    """
    Expose WebRTC ICE server configuration (STUN + optional TURN credentials from env)
    to frontend clients dynamically without exposing static hardcoded secrets.
    """
    ice_servers = [
        {"urls": "stun:stun.l.google.com:19302"},
        {"urls": "stun:stun1.l.google.com:19302"},
    ]
    if TURN_URL and TURN_URL.strip():
        turn_entry = {"urls": TURN_URL.strip()}
        if TURN_USERNAME and TURN_USERNAME.strip():
            turn_entry["username"] = TURN_USERNAME.strip()
        if TURN_CREDENTIAL and TURN_CREDENTIAL.strip():
            turn_entry["credential"] = TURN_CREDENTIAL.strip()
        ice_servers.append(turn_entry)

    return {"iceServers": ice_servers}


def _get_challenge_by_slug(slug: str, db: Session) -> Challenge | None:
    challenge = db.query(Challenge).filter(Challenge.slug == slug).first()
    if challenge is not None:
        return challenge
    return db.query(Challenge).filter(Challenge.folder_name == slug).first()


import time

# In-process TTL cache for list_active_challenges (TTL ~60s).
# NOTE: This cache is stored in-memory within this single process. If the backend is ever
# horizontally scaled to multiple worker processes/instances, replace this with a centralized
# Redis cache (similar to the in-memory WebSocket connection registry note in team_ws.py).
_challenges_cache = {}
_CHALLENGES_CACHE_TTL = 60.0  # seconds


@router.get("/challenges")
def list_active_challenges(mode: str | None = None, db: Session = Depends(get_db)):
    cache_key = mode or "all"
    now = time.time()
    if cache_key in _challenges_cache:
        cached_data, expiry = _challenges_cache[cache_key]
        if now < expiry:
            return cached_data

    query = db.query(Challenge).filter(Challenge.is_active == True)
    if mode in ("individual", "team"):
        query = query.filter(Challenge.mode == mode)
    challenges = query.order_by(Challenge.created_at.desc()).all()
    result = [
        {
            "id": c.id,
            "slug": c.slug,
            "title": c.title,
            "difficulty": c.difficulty,
            "category": c.category,
            "description": c.description,
            "time_limit": c.time_limit,
            "mode": c.mode or "individual",
            "team_size": c.team_size if c.team_size is not None else 1,
        }
        for c in challenges
    ]
    _challenges_cache[cache_key] = (result, now + _CHALLENGES_CACHE_TTL)
    return result


@router.get("/challenge/{slug}", response_model=ChallengeResponse)
def get_challenge(slug: str, db: Session = Depends(get_db)):
    challenge = _get_challenge_by_slug(slug, db)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge Not Found")
    return challenge


@router.get("/challenge/{slug}/details")
def get_challenge_details(slug: str, db: Session = Depends(get_db)):
    challenge = _get_challenge_by_slug(slug, db)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge Not Found")
    from services.gemini_service import _parse_constraints_list
    constraints_list = _parse_constraints_list(challenge.constraints)
    readme = (
        f"# {challenge.title}\n\n"
        f"**Category:** {challenge.category or 'General'}\n"
        f"**Difficulty:** {challenge.difficulty}\n\n"
        f"## Scenario\n{challenge.scenario}\n\n"
        f"## Rules\n{challenge.rules}\n"
    )
    return {
        "id": challenge.id, "slug": challenge.slug, "title": challenge.title,
        "difficulty": challenge.difficulty, "category": challenge.category,
        "scenario": challenge.scenario, "rules": challenge.rules,
        "time_limit": challenge.time_limit, "readme": readme,
        "constraints": constraints_list,
        "mode": challenge.mode or "individual",
        "team_size": challenge.team_size if challenge.team_size is not None else 1,
    }


@router.get("/challenge/{slug}/download")
def download_challenge(slug: str, db: Session = Depends(get_db)):
    import io, zipfile
    challenge = _get_challenge_by_slug(slug, db)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge Not Found")
    from services.gemini_service import _parse_constraints_list
    constraints_list = _parse_constraints_list(challenge.constraints)
    constraints_str = "\n".join(f"- {c}" for c in constraints_list) if constraints_list else "No constraints specified."

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.md", f"# {challenge.title}\n\n{challenge.scenario}\n\n## Rules\n{challenge.rules}")
        zf.writestr("constraints.txt", constraints_str)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{challenge.slug}.zip"'})