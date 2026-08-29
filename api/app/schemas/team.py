from pydantic import BaseModel, ConfigDict

from app.models.enums import League


class Team(BaseModel):
    id: int
    full_name: str
    abbreviation: str
    nickname: str
    city: str
    state: str
    year_founded: int
    league: League

    model_config = ConfigDict(from_attributes=True)
