from pathlib import Path
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from models.challenge import Challenge
from schemas.admin import AdminChallengeCreate


class ChallengeUploadService:
    ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets" / "challenges"

    def __init__(self, db: Session):
        self.db = db



    def create_challenge(self, payload: AdminChallengeCreate) -> Dict[str, object]:
        existing = self.db.query(Challenge).filter(Challenge.slug == payload.slug).first()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Challenge slug already exists",
            )
            
        challenge = Challenge(
            slug=payload.slug,
            title=payload.title,
            description=payload.description,
            scenario=payload.scenario,
            difficulty=payload.difficulty,
            rules=payload.rules,
            time_limit=payload.time_limit,
            category=payload.category,
            starter_code=payload.starter_code,
            official_solution=payload.official_solution,
            folder_name=payload.slug,
            is_active=True,
        )
        self.db.add(challenge)
        self.db.commit()
        self.db.refresh(challenge)
        return self._serialize(challenge)

    def list_challenges(self) -> List[Dict[str, object]]:
        challenges = self.db.query(Challenge).order_by(Challenge.created_at.desc()).all()
        return [self._serialize(challenge) for challenge in challenges]

    def get_challenge(self, challenge_id: int) -> Optional[Dict[str, object]]:
        challenge = self.db.query(Challenge).filter(Challenge.id == challenge_id).first()
        if challenge is None:
            return None
        return self._serialize_detail(challenge)

    def update_challenge(self, challenge_id: int, payload: Dict[str, object]) -> Dict[str, object]:
        challenge = self.db.query(Challenge).filter(Challenge.id == challenge_id).first()
        if challenge is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")

        for field in [
            "title",
            "description",
            "scenario",
            "difficulty",
            "rules",
            "time_limit",
            "is_active",
            "category",
            "starter_code",
            "official_solution",
        ]:
            if field in payload:
                setattr(challenge, field, payload[field])

        self.db.commit()
        self.db.refresh(challenge)
        return self._serialize(challenge)

    def delete_challenge(self, challenge_id: int) -> Dict[str, object]:
        challenge = self.db.query(Challenge).filter(Challenge.id == challenge_id).first()
        if challenge is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")

        challenge.is_active = False
        self.db.commit()
        self.db.refresh(challenge)
        return self._serialize(challenge)

    def _serialize(self, challenge: Challenge) -> Dict[str, object]:
        return {
            "id": challenge.id,
            "slug": challenge.slug,
            "title": challenge.title,
            "difficulty": challenge.difficulty or "Medium",
            "folder_name": challenge.folder_name or challenge.slug,
            "description": challenge.description or "",
            "scenario": challenge.scenario or "",
            "rules": challenge.rules or "",
            "time_limit": challenge.time_limit if challenge.time_limit is not None else 45,
            "is_active": challenge.is_active if challenge.is_active is not None else True,
            "created_at": challenge.created_at,
            "category": challenge.category or "",
        }

    def _serialize_detail(self, challenge: Challenge) -> Dict[str, object]:
        data = self._serialize(challenge)
        data["starter_code"] = challenge.starter_code or ""
        data["official_solution"] = challenge.official_solution or ""
        return data


