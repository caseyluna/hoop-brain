from fastapi import APIRouter

router = APIRouter()


@router.get("/teams")
def list_teams():
    """
    List all teams.
    """
    return {"message": "List of teams"}
