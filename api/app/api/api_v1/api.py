from fastapi import APIRouter

from app.api.routes import players, teams

router = APIRouter()
router.include_router(teams.router, prefix="/teams", tags=["teams"])
router.include_router(players.router, prefix="/players", tags=["players"])
