import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.api_v1.api import router as api_router

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

# Versioned API routes
app.include_router(api_router, prefix="/api/v1")
