from fastapi import FastAPI

from app.api import teams

app = FastAPI()
app.include_router(teams.router)
