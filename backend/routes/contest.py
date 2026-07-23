from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database.connection import get_db
from models.challenge import Challenge
from schemas.challenge import ChallengeResponse

router = APIRouter()

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def _get_challenge_by_slug(slug: str, db: Session) -> Challenge | None:
    challenge = db.query(Challenge).filter(Challenge.slug == slug).first()
    if challenge is not None:
        return challenge
    return db.query(Challenge).filter(Challenge.folder_name == slug).first()



@router.get("/challenges")
def list_active_challenges(db: Session = Depends(get_db)):
    challenges = db.query(Challenge).filter(Challenge.is_active == True).order_by(Challenge.created_at.desc()).all()
    return [
        {
            "slug": c.slug, "title": c.title, "difficulty": c.difficulty,
            "category": c.category, "description": c.description,
            "time_limit": c.time_limit,
        }
        for c in challenges
    ]


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
    }


@router.get("/challenge/{slug}/download")
def download_challenge(slug: str, db: Session = Depends(get_db)):
    import io, zipfile
    challenge = _get_challenge_by_slug(slug, db)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge Not Found")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.md", f"# {challenge.title}\n\n{challenge.scenario}\n\n## Rules\n{challenge.rules}")
        zf.writestr("starter_code.txt", challenge.starter_code or "")
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{challenge.slug}.zip"'})