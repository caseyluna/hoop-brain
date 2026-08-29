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
    state = Column(String, nullable=False)
    year_founded = Column(Integer, nullable=False)
    league = Column(
        Enum(League, name="league"),
        nullable=False,
        server_default=League.NBA.value,
    )
