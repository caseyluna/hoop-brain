import polars as pl
import pytest
from sqlalchemy import create_engine, inspect, text

from src.jobs.bq_to_postgres import BQToPostgresJob


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


def test_atomic_swap_casts_to_destination_column_type(test_engine):
    """
    write_to_postgres's auto-generated tmp table gets its column types from
    pandas/polars type inference (plain text for strings), which won't match
    a richer destination column type like a custom Postgres enum without an
    explicit cast — this reproduces that mismatch (as hit syncing the real
    `league` enum column) and confirms _atomic_swap casts correctly instead
    of raising a DatatypeMismatch.
    """
    with test_engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS cast_test_table"))
        conn.execute(text("DROP TYPE IF EXISTS cast_test_status"))
        conn.execute(
            text("CREATE TYPE cast_test_status AS ENUM ('ACTIVE', 'INACTIVE')")
        )
        conn.execute(
            text("CREATE TABLE cast_test_table (id INTEGER, status cast_test_status)")
        )

    job = BQToPostgresJob(
        bq_view="test_view",
        pg_table="cast_test_table",
        bq_client=None,
        pg_engine=test_engine,
    )
    df = pl.DataFrame({"id": [1, 2], "status": ["ACTIVE", "INACTIVE"]})
    tmp_table = "cast_test_table_tmp"
    job.write_to_postgres(df, tmp_table)
    job._atomic_swap(tmp_table)

    with test_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, status FROM cast_test_table ORDER BY id")
        ).fetchall()
    assert [tuple(row) for row in rows] == [(1, "ACTIVE"), (2, "INACTIVE")]

    with test_engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS cast_test_table"))
        conn.execute(text("DROP TYPE IF EXISTS cast_test_status"))
