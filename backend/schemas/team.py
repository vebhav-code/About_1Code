from pydantic import BaseModel, field_validator, model_validator
from typing import List, Optional


class TeamCreate(BaseModel):
    challenge_id: int
    user_id: int
    team_name: str

    @field_validator("team_name")
    @classmethod
    def validate_team_name(cls, v: str) -> str:
        s = v.strip() if v else ""
        if not s:
            raise ValueError("Team name cannot be empty or whitespace.")
        return s


class TeamJoin(BaseModel):
    user_id: int
    team_id: Optional[int] = None
    invite_code: Optional[str] = None

    @model_validator(mode="after")
    def validate_join_target(self):
        if (self.team_id is None and self.invite_code is None) or (self.team_id is not None and self.invite_code is not None):
            raise ValueError("Exactly one of team_id or invite_code must be provided.")
        if self.invite_code:
            self.invite_code = self.invite_code.strip()
        return self


class TeamMemberOut(BaseModel):
    user_id: int
    name: str

    class Config:
        from_attributes = True


class TeamResponse(BaseModel):
    id: int
    team_id: Optional[int] = None
    challenge_id: int
    name: str
    invite_code: str
    leader_user_id: int
    status: str
    team_size: int
    members: List[TeamMemberOut]

    @model_validator(mode="after")
    def populate_team_id(self):
        if self.team_id is None:
            self.team_id = self.id
        return self

    class Config:
        from_attributes = True


class TeamSummary(BaseModel):
    id: int
    team_id: Optional[int] = None
    name: str
    leader_name: str
    member_count: int
    team_size: int

    @model_validator(mode="after")
    def populate_team_id(self):
        if self.team_id is None:
            self.team_id = self.id
        return self

    class Config:
        from_attributes = True
