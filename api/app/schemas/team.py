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
    # nba_api's NBA teams (see app/models/team.py). Explicit `= None` default
    # matters here, not just style — without it Vercel's Python runtime
    # (which serializes the response through its own vendored, older
    # Pydantic/FastAPI rather than this project's locked version) rejects a
    # present-but-null value with a ResponseValidationError.
    state: Optional[str] = None
    year_founded: Optional[int] = None
    league: League

    model_config = ConfigDict(from_attributes=True)
