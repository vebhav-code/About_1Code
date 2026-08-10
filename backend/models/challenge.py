from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func

from database.connection import Base


class Challenge(Base):

    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True)

    slug = Column(String, unique=True)

    title = Column(String)

    difficulty = Column(String)

    folder_name = Column(String, index=True)
    category = Column(String)
    starter_code = Column(Text)
    official_solution = Column(Text)

    is_active = Column(Boolean, default=True, index=True)
    description = Column(String)
    scenario = Column(String)
    rules = Column(String)
    time_limit = Column(Integer)
    mode = Column(String, nullable=False, default="individual")
    team_size = Column(Integer, nullable=False, default=1)
    challenge_format = Column(String, nullable=False, default="debug")
    run_command = Column(String, nullable=True, default="pytest")

    created_at = Column(DateTime(timezone=True),
                        server_default=func.now())

    from sqlalchemy.orm import relationship
    files = relationship("ChallengeFile", back_populates="challenge", cascade="all, delete-orphan")