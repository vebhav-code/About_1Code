from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    hypothesis = Column(Integer, nullable=False)
    prompt_quality = Column(Integer, nullable=False)
    ai_collaboration = Column(Integer, nullable=False)
    code_correctness = Column(Integer, nullable=False)
    problem_solving = Column(Integer, nullable=False)
    total_score = Column(Integer, nullable=False)
    strengths = Column(JSON, nullable=False)
    improvements = Column(JSON, nullable=False)
    overall_feedback = Column(String, nullable=False)
    evaluated_at = Column(DateTime(timezone=True), server_default=func.now())

    submission = relationship("Submission")

    @property
    def late(self) -> bool:
        return self.submission.late if self.submission else False
