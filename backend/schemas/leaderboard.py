from pydantic import BaseModel
from typing import List, Optional


class LeaderboardEntryResponse(BaseModel):
    rank: int
    name: str
    score: int
    challenge: str
    submission_time: str
    team_name: Optional[str] = None
    members: Optional[List[str]] = None


class UserRankSummary(BaseModel):
    participated: bool
    rank: Optional[int] = None
    score: Optional[int] = None
    submission_id: Optional[int] = None


class LeaderboardResponse(BaseModel):
    challenge_slug: str
    challenge_title: str
    mode: str
    entries: List[LeaderboardEntryResponse]
    my_rank: Optional[UserRankSummary] = None


class UserRankResponse(BaseModel):
    current_rank: int
    current_score: int
    users_above: List[LeaderboardEntryResponse]
    users_below: List[LeaderboardEntryResponse]


class ChallengeStatsResponse(BaseModel):
    total_participants: int
    average_score: float
    highest_score: int
    lowest_score: int
    challenge_name: str
    challenge_slug: str
