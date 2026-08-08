from pathlib import Path
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from models.challenge import Challenge
from schemas.admin import AdminChallengeCreate


from models.submission import Submission
from models.team import Team


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
            mode=payload.mode,
            team_size=payload.team_size,
            folder_name=payload.slug,
            is_active=True,
        )
        self.db.add(challenge)
        self.db.commit()
        self.db.refresh(challenge)
        return self._serialize(challenge)

    def list_challenges(self, include_archived: bool = False) -> List[Dict[str, object]]:
        query = self.db.query(Challenge)
        if not include_archived:
            query = query.filter(Challenge.is_active == True)
        challenges = query.order_by(Challenge.created_at.desc()).all()
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

        merged_mode = payload.get("mode", challenge.mode or "individual")
        merged_team_size = payload.get("team_size", challenge.team_size if challenge.team_size is not None else 1)

        if merged_mode == "team" and (merged_team_size is None or merged_team_size < 2):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="team_size must be >= 2 when mode is 'team'",
            )
        if merged_mode == "individual" and merged_team_size != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="team_size must be 1 when mode is 'individual'",
            )

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
            "mode",
            "team_size",
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

        has_submissions = self.db.query(Submission).filter(Submission.challenge_id == challenge_id).first() is not None
        has_teams = self.db.query(Team).filter(Team.challenge_id == challenge_id).first() is not None

        if not has_submissions and not has_teams:
            self.db.delete(challenge)
            self.db.commit()
            return {
                "id": challenge_id,
                "deleted": True,
                "archived": False,
                "reason": "Challenge permanently deleted.",
            }
        else:
            challenge.is_active = False
            self.db.commit()
            return {
                "id": challenge_id,
                "deleted": False,
                "archived": True,
                "reason": "Challenge has existing submissions and was archived instead of deleted to preserve leaderboard/profile history.",
            }

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
            "mode": challenge.mode or "individual",
            "team_size": challenge.team_size if challenge.team_size is not None else 1,
        }

    def _serialize_detail(self, challenge: Challenge) -> Dict[str, object]:
        data = self._serialize(challenge)
        data["starter_code"] = challenge.starter_code or ""
        data["official_solution"] = challenge.official_solution or ""
        return data
