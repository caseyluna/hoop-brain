from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import League
from app.models.team import Team as TeamModel
from app.schemas.team import Team as TeamSchema

router = APIRouter()


@router.get("/", response_model=List[TeamSchema])
def get_teams(
    league: Optional[League] = Query(
        None, description="Filter by league. Omit to return both NBA and WNBA."
    ),
    db: Session = Depends(get_db),
):
    query = db.query(TeamModel)
    if league is not None:
        query = query.filter(TeamModel.league == league)
    return query.all()
