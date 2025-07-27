from pydantic import BaseModel, ConfigDict


class Team(BaseModel):
    id: int
    full_name: str
    abbreviation: str
    nickname: str
    city: str
    state: str
    year_founded: int

    model_config = ConfigDict(from_attributes=True)
