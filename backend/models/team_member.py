from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    team = relationship("Team", back_populates="members")
    user = relationship("User")
