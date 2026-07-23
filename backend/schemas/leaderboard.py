from pydantic import BaseModel
from typing import List


class LeaderboardEntryResponse(BaseModel):
    rank: int
    name: str
    score: int
    challenge: str
    submission_time: str


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
