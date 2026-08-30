# api/tests/conftest.py

import os

# Must run before importing app.main: both app.db.session and
# app.core.security read their env var at module-import time, so setting a
# fallback afterward wouldn't reach the already-captured module-level value.
os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "test")
os.environ["API_KEY"] = os.environ.get("API_KEY", "test-key")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    return TestClient(app, headers={"X-API-Key": os.environ["API_KEY"]})
