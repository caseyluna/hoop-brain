from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.team import Team as TeamModel
from app.schemas.team import Team as TeamSchema

router = APIRouter()


@router.get("/", response_model=List[TeamSchema])
def get_teams(db: Session = Depends(get_db)):
    return db.query(TeamModel).all()
