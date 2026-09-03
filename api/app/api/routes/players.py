from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import League
from app.models.player import Player as PlayerModel
from app.schemas.player import Player as PlayerSchema

router = APIRouter()


@router.get("/", response_model=List[PlayerSchema])
def get_players(
    league: Optional[League] = Query(
        None, description="Filter by league. Omit to return both NBA and WNBA."
    ),
    is_active: Optional[bool] = Query(None, description="Filter by active status."),
    team_id: Optional[int] = Query(None, description="Filter by current team."),
    search: Optional[str] = Query(
        None, description="Case-insensitive substring match on full_name."
    ),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return."),
    offset: int = Query(0, ge=0, description="Rows to skip, for pagination."),
    db: Session = Depends(get_db),
):
    query = db.query(PlayerModel)
    if league is not None:
        query = query.filter(PlayerModel.league == league)
    if is_active is not None:
        query = query.filter(PlayerModel.is_active == is_active)
    if team_id is not None:
        query = query.filter(PlayerModel.current_team_id == team_id)
    if search is not None:
        query = query.filter(PlayerModel.full_name.ilike(f"%{search}%"))
    return query.order_by(PlayerModel.id).offset(offset).limit(limit).all()


@router.get("/{player_id}", response_model=PlayerSchema)
def get_player(player_id: int, db: Session = Depends(get_db)):
    player = db.query(PlayerModel).filter(PlayerModel.id == player_id).first()
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return player
