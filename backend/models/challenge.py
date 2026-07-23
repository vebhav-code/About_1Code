from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func

from database.connection import Base


class Challenge(Base):

    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True)

    slug = Column(String, unique=True)

    title = Column(String)

    difficulty = Column(String)

    folder_name = Column(String)
    category = Column(String)
    starter_code = Column(Text)
    official_solution = Column(Text)

    is_active = Column(Boolean, default=True)
    description = Column(String)
    scenario = Column(String)
    rules = Column(String)
    time_limit = Column(Integer)

    created_at = Column(DateTime(timezone=True),
                        server_default=func.now())