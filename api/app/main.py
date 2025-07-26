from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.api_v1.api import router as api_router

app = FastAPI(
    title="Hoop Brain API",
    version="1.0.0",
)

# Optional: CORS setup for dev/local web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this in prod!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Versioned API routes
app.include_router(api_router, prefix="/api/v1")
