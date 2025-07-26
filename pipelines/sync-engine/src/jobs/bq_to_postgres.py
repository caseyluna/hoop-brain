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
            "Syncing BQ view `{self.bq_view}` -> Postgres table `{self.pg_table}`"
        )
        if self.dry_run:
            logger.info(f"[DRY RUN] Would sync {self.bq_view} to {self.pg_table}")
            return
        df = self._read_from_bq()
        tmp_table = f"{self.pg_table}_tmp"

        self._write_to_postgres(df, tmp_table)
        self._atomic_swap(tmp_table)

        logger.info(f"Synced {len(df)} rows from {self.bq_view} -> {self.pg_table}")

    def _read_from_bq(self) -> pl.DataFrame:
        query = f"SELECT * FROM `{self.bq_view}`"
        logger.info(f"Executing BQ query: {query}")
        result = self.bq_client.query(query).to_dataframe()
        logger.info(f"Retrieved {len(result)} rows from BQ view `{self.bq_view}`")
        return pl.from_pandas(result)

    def _write_to_postgres(self, df: pl.DataFrame, tmp_table: str) -> None:
        logger.info(f"Writing {len(df)} rows to temporary Postgres table `{tmp_table}`")
        with self.pg_engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {tmp_table}"))
            df.write_database(table_name=tmp_table, connection=conn)
        logger.info(f"Successfully wrote to temporary Postgres table `{tmp_table}`")

    def _atomic_swap(self, tmp_table: str) -> None:
        inspector = inspect(self.pg_engine)
        existing_tables = inspector.get_table_names()
        with self.pg_engine.begin() as conn:
            if self.pg_table in existing_tables:
                logger.info(f"Truncating existing table {self.pg_table}")
                conn.execute(text(f"TRUNCATE TABLE {self.pg_table}"))
            else:
                logger.info(f"Creating new table {self.pg_table} from {tmp_table}")
                conn.execute(text(f"ALTER TABLE {tmp_table} RENAME TO {self.pg_table}"))
                return
            logger.info(f"Inserting into {self.pg_table} from {tmp_table}")
            conn.execute(
                text(f'INSERT INTO "{self.pg_table}" SELECT * FROM "{tmp_table}"')
            )

            logger.info(f"Dropping temp table `{tmp_table}`")
            conn.execute(text(f'DROP TABLE IF EXISTS "{tmp_table}"'))
