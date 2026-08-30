import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.api_v1.api import router as api_router
from app.core.security import require_api_key

app = FastAPI(
    title="Hoop Brain API",
    version="1.0.0",
)


@app.get("/health")
def health():
    """Health check for load balancers and monitoring."""
    return {"status": "ok"}


# CORS_ORIGINS: comma-separated allowed origins (set in Vercel env for prod).
# Unset locally falls back to "*" for dev convenience.
_cors_origins_env = os.getenv("CORS_ORIGINS")
_allow_origins = (
    [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]
    if _cors_origins_env
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Versioned API routes — gated by a shared API key (see app/core/security.py).
# /health and the auto-generated docs (/docs, /redoc, /openapi.json) stay
# open: they don't touch the database, so there's nothing to spam or protect.
app.include_router(
    api_router, prefix="/api/v1", dependencies=[Depends(require_api_key)]
)
