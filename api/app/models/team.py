from sqlalchemy import Column, Enum, Integer, String

from app.db.base import Base
from app.models.enums import League


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    abbreviation = Column(String, nullable=False)
    nickname = Column(String, nullable=False)
    city = Column(String, nullable=False)
    # Nullable: ESPN's WNBA teams source doesn't publish either field, unlike
    # nba_api's NBA teams (see stg_wehoop__teams.sql in transformation-engine).
    state = Column(String, nullable=True)
    year_founded = Column(Integer, nullable=True)
    league = Column(
        Enum(League, name="league"),
        nullable=False,
        server_default=League.NBA.value,
    )
