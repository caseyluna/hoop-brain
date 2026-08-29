from sqlalchemy import Column, Integer, String

from app.db.base import Base


class Team(Base):
    __tablename__ = "teams"

    league = Column(String, nullable=False, server_default="NBA")
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    abbreviation = Column(String, nullable=False)
    nickname = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    year_founded = Column(Integer, nullable=False)
