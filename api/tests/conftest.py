# api/tests/conftest.py

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    # Ensure DATABASE_URL is set before importing app/db code
    os.getenv("DATABASE_URL")
    return TestClient(app)
