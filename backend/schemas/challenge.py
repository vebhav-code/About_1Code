from pydantic import BaseModel


class ChallengeResponse(BaseModel):

    id: int

    slug: str

    title: str

    difficulty: str

    folder_name: str

    class Config:

        from_attributes = True