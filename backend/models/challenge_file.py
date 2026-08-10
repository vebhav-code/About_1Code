from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base


class ChallengeFile(Base):
    __tablename__ = "challenge_files"
    __table_args__ = (
        UniqueConstraint("challenge_id", "filename", name="uq_challenge_filename"),
        Index("idx_challenge_files_challenge_filename", "challenge_id", "filename"),
    )

    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    file_order = Column(Integer, default=0, nullable=False)
    starter_content = Column(Text, nullable=False, default="")
    solution_content = Column(Text, nullable=False, default="")
    language = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    challenge = relationship("Challenge", back_populates="files")
