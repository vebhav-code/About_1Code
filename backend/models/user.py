from sqlalchemy import Column, Integer, String, DateTime, Boolean, Date, Text
from sqlalchemy.sql import func
from database.connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_banned = Column(Boolean, default=False, nullable=False)
    banned_reason = Column(Text, nullable=True)
    banned_at = Column(DateTime(timezone=True), nullable=True)
    avatar_url = Column(String(512), default="", nullable=True)
    bio = Column(Text, default="", nullable=True)
    github_url = Column(String(255), default="", nullable=True)
    linkedin_url = Column(String(255), default="", nullable=True)
    website_url = Column(String(255), default="", nullable=True)
    current_streak = Column(Integer, default=0, nullable=False)
    longest_streak = Column(Integer, default=0, nullable=False)
    last_active_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "is_admin": self.is_admin,
            "is_banned": self.is_banned,
            "banned_reason": self.banned_reason,
            "banned_at": self.banned_at.isoformat() if self.banned_at else None,
            "bio": self.bio or "",
            "github_url": self.github_url or "",
            "linkedin_url": self.linkedin_url or "",
            "website_url": self.website_url or "",
            "avatar_url": self.avatar_url or "",
            "current_streak": self.current_streak or 0,
            "longest_streak": self.longest_streak or 0,
            "last_active_date": self.last_active_date.isoformat() if self.last_active_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }