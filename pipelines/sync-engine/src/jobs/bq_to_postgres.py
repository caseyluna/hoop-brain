import logging
import sys
from dataclasses import dataclass
from typing import Optional

import polars as pl
from google.cloud import bigquery
from sqlalchemy import Engine, inspect, text

from src.jobs.base import BaseJob

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


@dataclass
class BQToPostgresJob(BaseJob):
    bq_view: str
    pg_table: str
    bq_client: bigquery.Client
    pg_engine: Engine
    primary_key: Optional[str] = None
    dry_run: bool = False

    def run(self) -> None:
        logger.info(
            f"Syncing BQ view `{self.bq_view}` -> Postgres table `{self.pg_table}`"
        )
        if self.dry_run:
            logger.info(f"[DRY RUN] Would sync {self.bq_view} to {self.pg_table}")
            return
        df = self._read_from_bq()
        tmp_table = f"{self.pg_table}_tmp"

        self.write_to_postgres(df, tmp_table)
        self._atomic_swap(tmp_table)

        logger.info(f"Synced {len(df)} rows from {self.bq_view} -> {self.pg_table}")

    def _read_from_bq(self) -> pl.DataFrame:
        query = f"SELECT * FROM `{self.bq_view}`"
        logger.info(f"Executing BQ query: {query}")
        result = self.bq_client.query(query).to_dataframe()
        logger.info(f"Retrieved {len(result)} rows from BQ view `{self.bq_view}`")
        return pl.from_pandas(result)

    def write_to_postgres(self, df: pl.DataFrame, tmp_table: str) -> None:
        logger.info(f"Writing {len(df)} rows to temporary Postgres table `{tmp_table}`")
        with self.pg_engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {tmp_table}"))
            df.write_database(table_name=tmp_table, connection=conn)
        logger.info(f"Successfully wrote to temporary Postgres table `{tmp_table}`")

    def _atomic_swap(self, tmp_table: str) -> None:
        inspector = inspect(self.pg_engine)
        existing_tables = inspector.get_table_names()
        pg_table_exists = self.pg_table in existing_tables

        # Reflect column types before opening the swap transaction below — once
        # that transaction deletes pg_table's rows, a second pooled connection
        # (which is what an Engine-bound inspector checks out to reflect) would
        # block on the still-uncommitted DELETE's lock, deadlocking against itself.
        select_list = (
            self._build_cast_select_list(inspector, tmp_table)
            if pg_table_exists
            else None
        )

        with self.pg_engine.begin() as conn:
            if pg_table_exists:
                # DELETE, not TRUNCATE (CAL-150): TRUNCATE refuses outright,
                # regardless of deferrable settings, when another table (e.g.
                # players.current_team_id -> teams.id) currently references
                # this one -- Postgres treats it as a DDL-level operation, not
                # subject to per-row/deferred FK checking. Plain DELETE inside
                # this same transaction respects a DEFERRABLE INITIALLY
                # DEFERRED FK instead: the momentary gap while rows are
                # replaced is only checked at COMMIT, by which point the
                # reinserted rows (same ids) satisfy it again.
                logger.info(f"Deleting existing rows from {self.pg_table}")
                conn.execute(text(f'DELETE FROM "{self.pg_table}"'))
            else:
                logger.info(f"Creating new table {self.pg_table} from {tmp_table}")
                conn.execute(text(f"ALTER TABLE {tmp_table} RENAME TO {self.pg_table}"))
                return
            logger.info(f"Inserting into {self.pg_table} from {tmp_table}")
            conn.execute(
                text(
                    f'INSERT INTO "{self.pg_table}" SELECT {select_list} FROM "{tmp_table}"'
                )
            )

            logger.info(f"Dropping temp table `{tmp_table}`")
            conn.execute(text(f'DROP TABLE IF EXISTS "{tmp_table}"'))

    def _build_cast_select_list(self, inspector, tmp_table: str) -> str:
        """
        Build a SELECT list that casts each tmp_table column to the destination
        table's actual Postgres column type.

        write_to_postgres's auto-generated tmp table gets its types from
        pandas/polars type inference (e.g. everything lands as plain text),
        which won't match a richer destination type — a custom enum like
        `league`, for instance — without an explicit cast.
        """
        tmp_columns = [col["name"] for col in inspector.get_columns(tmp_table)]
        dest_types = {
            col["name"]: col["type"].compile(dialect=self.pg_engine.dialect)
            for col in inspector.get_columns(self.pg_table)
        }
        return ", ".join(
            f'"{col}"::{dest_types[col]}' if col in dest_types else f'"{col}"'
            for col in tmp_columns
        )
