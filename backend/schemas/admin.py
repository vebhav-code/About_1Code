from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class AdminChallengeBase(BaseModel):
    title: str
    description: str
    scenario: str
    difficulty: str
    rules: str
    time_limit: int
    category: str
    starter_code: str
    official_solution: str


class AdminChallengeCreate(AdminChallengeBase):
    slug: str

    @field_validator("slug")
    @classmethod
    def sanitize_slug(cls, value: str) -> str:
        # Strip whitespace (spaces, tabs, newlines) that can sneak in from
        # copy-pasting, and collapse to a clean, database-safe slug.
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Slug cannot be empty or whitespace only")
        return cleaned


class AdminChallengeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    scenario: Optional[str] = None
    difficulty: Optional[str] = None
    rules: Optional[str] = None
    time_limit: Optional[int] = None
    is_active: Optional[bool] = None
    category: Optional[str] = None
    starter_code: Optional[str] = None
    official_solution: Optional[str] = None


class AdminChallengeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    difficulty: str
    folder_name: str
    description: Optional[str] = ""
    scenario: Optional[str] = ""
    rules: Optional[str] = ""
    time_limit: Optional[int] = 45
    is_active: bool
    created_at: datetime
    category: Optional[str] = ""

class AdminChallengeDetailResponse(AdminChallengeResponse):
    starter_code: str = ""
    official_solution: str = ""
