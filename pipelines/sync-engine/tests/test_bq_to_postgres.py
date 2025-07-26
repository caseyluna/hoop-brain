import polars as pl
import pytest
from sqlalchemy import create_engine, inspect

from jobs.bq_to_postgres import BQToPostgresJob


@pytest.fixture()
def test_engine():
    # Create a test database engine
    engine = create_engine("postgresql://user:password@localhost/test_db")
    yield engine
    engine.dispose()


@pytest.fixture()
def sample_df():
    return pl.DataFrame(
        {
            "id": [1, 2, 3],
            "name": ["Team A", "Team B", "Team C"],
        }
    )


def test_write_to_postgres_creates_table(test_engine, sample_df):
    job = BQToPostgresJob(
        bq_view="test_view",
        pg_table="test_table",
        bq_client=None,  # Mock or pass a real client if needed
        pg_engine=test_engine,
    )
    job.write_to_postgres(sample_df, "test_table")
    inspector = inspect(test_engine)
    tables = inspector.get_table_names()
    assert "test_table" in tables
