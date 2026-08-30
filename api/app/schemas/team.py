from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import League


class Team(BaseModel):
    id: int
    full_name: str
    abbreviation: str
    nickname: str
    city: str
    # Optional: ESPN's WNBA teams source doesn't publish either field, unlike
    # nba_api's NBA teams (see app/models/team.py).
    state: Optional[str]
    year_founded: Optional[int]
    league: League

    model_config = ConfigDict(from_attributes=True)
