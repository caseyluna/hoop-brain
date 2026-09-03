from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import League


class Player(BaseModel):
    id: int
    league: League
    full_name: str
    birthdate: Optional[date]
    position: Optional[str]
    height: Optional[str]
    current_team_id: Optional[int]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
