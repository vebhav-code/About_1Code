from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ChallengeFileInput(BaseModel):
    filename: str
    starter_content: str
    solution_content: str
    file_order: int = 0
    language: Optional[str] = None

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        from utils.file_validation import validate_challenge_filename
        return validate_challenge_filename(value)


class AdminChallengeBase(BaseModel):
    title: str
    description: str
    scenario: str
    difficulty: str
    rules: str
    time_limit: int
    category: str
    starter_code: Optional[str] = ""
    official_solution: Optional[str] = ""
    run_command: Optional[str] = "pytest"
    files: list[ChallengeFileInput] = []
    mode: Literal["individual", "team"] = "individual"
    team_size: int = 1
    challenge_format: Literal["debug", "build"] = "debug"


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

    @field_validator("team_size")
    @classmethod
    def validate_team_size(cls, value: int, info) -> int:
        mode = info.data.get("mode", "individual")
        if mode == "team" and value < 2:
            raise ValueError("team_size must be >= 2 when mode is 'team'")
        if mode == "individual" and value != 1:
            raise ValueError("team_size must be 1 when mode is 'individual'")
        return value


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
    run_command: Optional[str] = None
    files: Optional[list[ChallengeFileInput]] = None
    mode: Optional[Literal["individual", "team"]] = None
    team_size: Optional[int] = None
    challenge_format: Optional[Literal["debug", "build"]] = None

    @field_validator("team_size")
    @classmethod
    def validate_team_size(cls, value: Optional[int], info) -> Optional[int]:
        if value is None:
            return value
        mode = info.data.get("mode")
        if mode is not None:
            if mode == "team" and value < 2:
                raise ValueError("team_size must be >= 2 when mode is 'team'")
            if mode == "individual" and value != 1:
                raise ValueError("team_size must be 1 when mode is 'individual'")
        return value


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
    run_command: Optional[str] = "pytest"
    files: list[ChallengeFileInput] = []
    mode: str = "individual"
    team_size: int = 1
    challenge_format: str = "debug"


class AdminChallengeDetailResponse(AdminChallengeResponse):
    starter_code: str = ""
    official_solution: str = ""




class AdminChallengeDeleteResponse(BaseModel):
    id: int
    deleted: bool
    archived: bool
    reason: str


class AdminUserSummary(BaseModel):
    id: int
    name: str
    email: str
    is_admin: bool
    is_banned: bool
    banned_reason: Optional[str] = None
    banned_at: Optional[datetime] = None
    created_at: datetime
    total_attempted: int = 0
    total_completed: int = 0


class AdminUserDetailResponse(BaseModel):
    id: int
    name: str
    email: str
    bio: Optional[str] = ""
    avatar_url: Optional[str] = None
    joined_at: Optional[datetime] = None
    is_admin: bool = False
    is_banned: bool = False
    banned_reason: Optional[str] = None
    banned_at: Optional[datetime] = None
    rank: Optional[int] = None
    percentile: Optional[int] = None
    average_score: int = 0
    weighted_points: int = 0
    total_attempted: int = 0
    total_completed: int = 0
    current_streak: int = 0
    longest_streak: int = 0
    history: list[dict] = []
    badges: list[dict] = []
    category_breakdown: list[dict] = []
    difficulty_breakdown: dict = {}
    visit_calendar: list[dict] = []


class AdminBanRequest(BaseModel):
    reason: Optional[str] = None
