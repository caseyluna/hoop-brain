import os
import secrets

from fastapi import Header, HTTPException, status

API_KEY = os.getenv("API_KEY")


def require_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> None:
    """
    Single shared-secret gate for /api/v1/*. This is a single-user tool (see
    CLAUDE.md non-goals: no multi-user auth), so one static key is enough to
    keep the public off it without building out real user auth — the goal is
    keeping anonymous traffic/spam off, not protecting sensitive data (the
    underlying data is public NBA/WNBA stats).
    """
    if not API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_KEY is not configured on the server",
        )
    if not x_api_key or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
