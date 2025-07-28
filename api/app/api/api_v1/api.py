from fastapi import APIRouter

from app.api.routes import teams

router = APIRouter()
router.include_router(teams.router, prefix="/teams", tags=["teams"])
