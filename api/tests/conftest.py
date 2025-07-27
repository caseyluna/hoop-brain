# api/tests/conftest.py

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "test")


@pytest.fixture(scope="session")
def client():
    return TestClient(app)
