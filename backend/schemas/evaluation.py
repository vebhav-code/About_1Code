from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class TeamMemberInfo(BaseModel):
    user_id: int
    name: str


class EvaluationResponse(BaseModel):
    id: int
    submission_id: int
    hypothesis: int = 0
    prompt_quality: int
    open_source_usage: int
    optimization: int
    topic_knowledge: int
    total_score: int
    strengths: List[str]
    improvements: List[str]
    overall_feedback: str
    late: bool = False
    evaluated_at: datetime

    user_name: Optional[str] = None
    team_name: Optional[str] = None
    members: Optional[List[TeamMemberInfo]] = None

    class Config:
        from_attributes = True
