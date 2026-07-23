from pydantic import BaseModel
from typing import List
from datetime import datetime


class EvaluationResponse(BaseModel):
    id: int
    submission_id: int
    hypothesis: int
    prompt_quality: int
    ai_collaboration: int
    code_correctness: int
    problem_solving: int
    total_score: int
    strengths: List[str]
    improvements: List[str]
    overall_feedback: str
    late: bool = False
    evaluated_at: datetime

    class Config:
        from_attributes = True
