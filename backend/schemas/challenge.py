import json
from pydantic import BaseModel, ConfigDict, field_validator


class ChallengeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    difficulty: str
    folder_name: str
    mode: str = "individual"
    team_size: int = 1
    constraints: list[str] = []

    @field_validator("constraints", mode="before")
    @classmethod
    def parse_constraints(cls, v):
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []
        if isinstance(v, list):
            return v
        return []