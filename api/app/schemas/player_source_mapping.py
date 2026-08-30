from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import League, MatchMethod


class PlayerSourceMapping(BaseModel):
    id: int
    internal_player_id: int
    league: League
    source: str
    source_id: str
    match_method: MatchMethod
    confidence: float
    matched_at: datetime

    model_config = ConfigDict(from_attributes=True)
