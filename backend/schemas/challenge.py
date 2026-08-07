from pydantic import BaseModel, ConfigDict


class ChallengeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    difficulty: str
    folder_name: str
    mode: str = "individual"
    team_size: int = 1