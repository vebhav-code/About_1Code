"""
schemas/submission.py
Pydantic schemas for submissions and approach evaluation responses.
"""

from datetime import datetime
from pydantic import BaseModel


class SubmissionResponse(BaseModel):
    submission_id: int
    overall_score: int
    feedback: str
    late: bool = False


class SubmissionOut(BaseModel):
    id: int
    challenge_id: int
    approach_text: str = ""
    late: bool = False
    submitted_at: datetime

    class Config:
        from_attributes = True
