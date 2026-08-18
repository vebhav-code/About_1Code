from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False, index=True)
    fixed_project_path = Column(String, nullable=True)
    debug_log_path = Column(String, nullable=True)
    late = Column(Boolean, nullable=False, default=False)
    topic_knowledge_score = Column(Integer, nullable=False, default=0)
    prompt_quality_score = Column(Integer, nullable=False, default=0)
    open_source_usage_score = Column(Integer, nullable=False, default=0)
    optimization_score = Column(Integer, nullable=False, default=0)
    overall_score = Column(Integer, nullable=False, default=0)
    approach_text = Column(Text, nullable=True, default="")
    feedback = Column(Text, nullable=False, default="")
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
