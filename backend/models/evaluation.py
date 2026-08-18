from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    hypothesis = Column(Integer, nullable=False, default=0)
    prompt_quality = Column(Integer, nullable=False)
    open_source_usage = Column(Integer, nullable=False)
    optimization = Column(Integer, nullable=False)
    topic_knowledge = Column(Integer, nullable=False)
    total_score = Column(Integer, nullable=False)
    strengths = Column(JSON, nullable=False)
    improvements = Column(JSON, nullable=False)
    overall_feedback = Column(String, nullable=False)
    evaluated_at = Column(DateTime(timezone=True), server_default=func.now())

    submission = relationship("Submission")

    @property
    def late(self) -> bool:
        return self.submission.late if self.submission else False
