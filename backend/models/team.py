from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    name = Column(String, nullable=False)
    invite_code = Column(String, unique=True, nullable=False, index=True)
    leader_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, nullable=False, default="forming")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    challenge = relationship("Challenge")
    leader = relationship("User", foreign_keys=[leader_user_id])
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
