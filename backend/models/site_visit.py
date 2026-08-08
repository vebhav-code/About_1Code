from sqlalchemy import Column, Date, Integer
from database.connection import Base


class SiteVisit(Base):
    __tablename__ = "site_visits"

    visit_date = Column(Date, primary_key=True)
    count = Column(Integer, default=0, nullable=False)
