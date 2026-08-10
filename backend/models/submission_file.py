from sqlalchemy import Column, Integer, String, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from database.connection import Base


class SubmissionFile(Base):
    __tablename__ = "submission_files"
    __table_args__ = (
        UniqueConstraint("submission_id", "filename", name="uq_submission_filename"),
        Index("idx_submission_files_submission_filename", "submission_id", "filename"),
    )

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    content = Column(Text, nullable=False, default="")

    submission = relationship("Submission", back_populates="files")
