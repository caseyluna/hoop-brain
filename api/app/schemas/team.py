from pydantic import BaseModel


class Team(BaseModel):
    id: int
    full_name: str
    abbreviation: str
    nickname: str
    city: str
    state: str
    year_founded: int

    class Config:
        orm_mode = True
