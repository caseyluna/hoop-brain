import polars as pl
import pytest
from sqlalchemy import create_engine, text

from src.jobs.player_resolver import PlayerResolverJob


@pytest.fixture()
def test_engine():
    engine = create_engine("postgresql://user:password@localhost/test_db")
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def scratch_schema(test_engine):
    # Minimal scratch schema, independent of the app's real Alembic-managed
    # league/match_method enums (same philosophy as test_bq_to_postgres.py's
    # cast_test_status) - plain TEXT columns are enough to exercise the
    # resolver's logic without depending on migration state.
    with test_engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS player_source_mapping"))
        conn.execute(text("DROP TABLE IF EXISTS players"))
        conn.execute(text("DROP TABLE IF EXISTS teams"))
        conn.execute(text("CREATE TABLE teams (id INTEGER PRIMARY KEY)"))
        conn.execute(
            text(
                "CREATE TABLE players ("
                "id SERIAL PRIMARY KEY, league TEXT NOT NULL, full_name TEXT NOT NULL, "
                "current_team_id INTEGER REFERENCES teams(id) DEFERRABLE INITIALLY DEFERRED, "
                "is_active BOOLEAN NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE player_source_mapping ("
                "id SERIAL PRIMARY KEY, internal_player_id INTEGER NOT NULL REFERENCES players(id), "
                "league TEXT NOT NULL, source TEXT NOT NULL, source_id TEXT NOT NULL, "
                "match_method TEXT NOT NULL, confidence FLOAT NOT NULL, "
                "matched_at TIMESTAMPTZ NOT NULL, "
                "UNIQUE (league, source, source_id))"
            )
        )
        conn.execute(text("INSERT INTO teams (id) VALUES (1), (2)"))
    yield
    with test_engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS player_source_mapping"))
        conn.execute(text("DROP TABLE IF EXISTS players"))
        conn.execute(text("DROP TABLE IF EXISTS teams"))


def sample_df(team_id=1):
    return pl.DataFrame(
        {
            "id": [100, 200],
            "league": ["NBA", "WNBA"],
            "full_name": ["Test Player One", "Test Player Two"],
            "team_id": [team_id, team_id],
            "is_active": [True, False],
        }
    )


class FakeBQResult:
    def __init__(self, df: pl.DataFrame):
        self._df = df

    def to_dataframe(self):
        return self._df.to_pandas()


class FakeBQClient:
    def __init__(self, df: pl.DataFrame):
        self._df = df

    def query(self, _query):
        return FakeBQResult(self._df)


def test_first_run_mints_new_players_and_mappings(test_engine):
    job = PlayerResolverJob(
        bq_view="marts.players",
        bq_client=FakeBQClient(sample_df()),
        pg_engine=test_engine,
    )
    job.run()

    with test_engine.connect() as conn:
        player_count = conn.execute(text("SELECT COUNT(*) FROM players")).scalar_one()
        mapping_count = conn.execute(
            text("SELECT COUNT(*) FROM player_source_mapping")
        ).scalar_one()
        confidences = conn.execute(
            text("SELECT DISTINCT confidence, match_method FROM player_source_mapping")
        ).fetchall()

    assert player_count == 2
    assert mapping_count == 2
    assert confidences == [(1.0, "tier1_passthrough")]


def test_second_run_is_idempotent(test_engine):
    df = sample_df()
    job = PlayerResolverJob(
        bq_view="marts.players", bq_client=FakeBQClient(df), pg_engine=test_engine
    )
    job.run()
    job.run()

    with test_engine.connect() as conn:
        player_count = conn.execute(text("SELECT COUNT(*) FROM players")).scalar_one()
        mapping_count = conn.execute(
            text("SELECT COUNT(*) FROM player_source_mapping")
        ).scalar_one()
        low_confidence = conn.execute(
            text("SELECT COUNT(*) FROM player_source_mapping WHERE confidence < 1.0")
        ).scalar_one()

    assert player_count == 2
    assert mapping_count == 2
    assert low_confidence == 0


def test_second_run_updates_mutable_fields_on_same_internal_id(test_engine):
    job = PlayerResolverJob(
        bq_view="marts.players",
        bq_client=FakeBQClient(sample_df(team_id=1)),
        pg_engine=test_engine,
    )
    job.run()
    with test_engine.connect() as conn:
        first_ids = conn.execute(
            text("SELECT id, current_team_id FROM players ORDER BY id")
        ).fetchall()

    job2 = PlayerResolverJob(
        bq_view="marts.players",
        bq_client=FakeBQClient(sample_df(team_id=2)),
        pg_engine=test_engine,
    )
    job2.run()
    with test_engine.connect() as conn:
        second_ids = conn.execute(
            text("SELECT id, current_team_id FROM players ORDER BY id")
        ).fetchall()

    assert [r.id for r in first_ids] == [r.id for r in second_ids]
    assert all(r.current_team_id == 2 for r in second_ids)


def test_invalid_team_id_nulled_not_fatal(test_engine):
    df = sample_df(team_id=99999)  # not in the teams table
    job = PlayerResolverJob(
        bq_view="marts.players", bq_client=FakeBQClient(df), pg_engine=test_engine
    )
    job.run()

    with test_engine.connect() as conn:
        team_ids = conn.execute(text("SELECT current_team_id FROM players")).fetchall()

    assert all(r.current_team_id is None for r in team_ids)
