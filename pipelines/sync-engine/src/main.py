import argparse
import logging
import os
import sys

import yaml
from google.cloud import bigquery
from sqlalchemy import create_engine

from src.jobs.bq_to_postgres import BQToPostgresJob

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def load_config(path="src/config/sync_jobs.yaml"):
    with open(path, "r") as file:
        return yaml.safe_load(file)


def run_bq_to_postgres_jobs(dry_run=False):
    bq_client = bigquery.Client()
    pg_engine = create_engine(os.environ["DATABASE_URL"])

    job_configs = load_config().get("bq_to_postgres", [])
    for config in job_configs:
        job = BQToPostgresJob(
            bq_view=config["bq_view"],
            pg_table=config["pg_table"],
            primary_key=config.get("primary_key"),
            bq_client=bq_client,
            pg_engine=pg_engine,
            dry_run=dry_run,
        )
        job.run()


def main():
    parser = argparse.ArgumentParser(description="Run sync jobs")
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run mode")
    args = parser.parse_args()
    run_bq_to_postgres_jobs(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
