"""
schemas/submission.py
Pydantic schemas for submissions and upload responses.
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
    fixed_project_path: str
    debug_log_path: str
    late: bool = False
    submitted_at: datetime

    class Config:
        from_attributes = True
