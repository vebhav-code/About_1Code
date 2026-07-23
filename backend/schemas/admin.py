from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


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
