from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class TeamMemberInfo(BaseModel):
    user_id: int
    name: str


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

    # --- Result page: who submitted ---
    user_name: Optional[str] = None
    team_name: Optional[str] = None
    members: Optional[List[TeamMemberInfo]] = None

    class Config:
        from_attributes = True
