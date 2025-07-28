# infra/dagger/cli.py

import argparse
import os
import sys
import time

import anyio
import dagger
import yaml
from utils import (
    check_passed,
    flatten_results,
    pretty_print,
    print_summary,
    status_emoji,
)

# Constants for database URLs
PROD_DB_URL = "postgresql://postgres:postgres@db:5432/hoopbrain"
TEST_DB_URL = "postgresql://postgres:postgres@db:5432/hoopbrain_test"


def load_yaml(path: str):
    with open(path) as f:
        return yaml.safe_load(f)


# Load service and pipeline configs
SERVICES = load_yaml("services.yaml")["services"]
PIPELINES = load_yaml("pipelines.yaml")["pipelines"]


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Dagger CLI")
    parser.add_argument(
        "--env", choices=["test", "prod"], default="test", help="DB environment"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # one subparser per pipeline key
    for pipeline in PIPELINES:
        subparsers.add_parser(pipeline, help=f"Run pipeline `{pipeline}`")

    # "job" to run individual service jobs
    job = subparsers.add_parser("job", help="Run a single job for a service")
    job.add_argument("service", choices=SERVICES.keys(), help="Service name")
    job.add_argument("job", help="Job name to run")

    return parser


async def start_db_service(client: dagger.Client, db_url: str):
    db_conf = SERVICES["db"]
    container = (
        client.container()
        .build(
            context=client.host().directory(db_conf["src_dir"]),
            dockerfile=db_conf.get("dockerfile", "Dockerfile"),
        )
        .with_env_variable("POSTGRES_DB", db_url.rsplit("/", 1)[-1])
        .with_env_variable("POSTGRES_USER", "postgres")
        .with_env_variable("POSTGRES_PASSWORD", "postgres")
        .with_exposed_port(5432)
        .as_service()
    )
    return container


async def run_job(
    client: dagger.Client,
    service: str,
    job: str,
    db_url: str = None,
    db_service: dagger.Container = None,
):
    conf = SERVICES[service]
    container = client.container().build(
        context=client.host().directory(conf["src_dir"]),
        dockerfile=conf.get("dockerfile", "Dockerfile"),
    )

    # Mount the GCP key file via Dagger secret
    # (we'll register the secret in main())
    container = container.with_secret_variable(
        "GCP_SA_JSON",
        client.set_secret("GCP_SA_JSON", os.getenv("GCP_SERVICE_ACCOUNT_JSON", "")),
    )
    container = await container.with_exec(
        [
            "bash",
            "-lc",
            "mkdir -p /app/keys && printf '%s' \"$GCP_SA_JSON\" > /app/keys/service_account.json",
        ]
    )
    container = container.with_env_variable(
        "GOOGLE_APPLICATION_CREDENTIALS", "/app/keys/service_account.json"
    )

    # Mount DBT profiles if needed
    if service == "transformation-engine":
        profiles_host = client.host().directory(f"{conf['src_dir']}/profiles")
        container = container.with_mounted_directory("/app/profiles", profiles_host)

    # Set DATABASE_URL if provided
    if db_url:
        container = container.with_env_variable("DATABASE_URL", db_url)

    # Bind DB service if this service depends on it
    if db_service and "db" in conf.get("dependencies", []):
        container = container.with_service_binding("db", db_service)

    # Execute the job
    command = conf["jobs"][job]
    start = time.perf_counter()
    result = await container.with_exec(command).stdout()
    elapsed = time.perf_counter() - start

    await pretty_print(service, job, result)
    passed = check_passed(result)
    return {
        "service": service,
        "job": job,
        "status": status_emoji(passed),
        "elapsed": elapsed,
    }


async def run_pipeline(
    client: dagger.Client,
    pipeline: str,
    db_url: str = None,
):
    steps = PIPELINES[pipeline]["steps"]
    results = []
    db_service = None

    # If any step needs the DB, start it once
    needs_db = any(
        "db" in SERVICES[s].get("dependencies", []) for step in steps for s in step
    )
    if needs_db:
        db_service = await start_db_service(client, db_url)

    # Run each job
    for step in steps:
        for service, jobs in step.items():
            for job in jobs:
                res = await run_job(client, service, job, db_url, db_service)
                results.append(res)

    return results


async def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    db_url = PROD_DB_URL if args.env == "prod" else TEST_DB_URL

    # Ensure the env var is set
    sa_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        print("ERROR: GCP_SERVICE_ACCOUNT_JSON env var not set")
        sys.exit(1)

    async with dagger.Connection() as client:
        # Register the JSON string as a Dagger secret
        client.set_secret("GCP_SA_JSON", sa_json)

        overall_start = time.perf_counter()

        if args.command == "job":
            results = [await run_job(client, args.service, args.job, db_url, None)]
        else:
            results = await run_pipeline(client, args.command, db_url)

        overall_duration = time.perf_counter() - overall_start
        summary = flatten_results(results)
        print_summary(summary, overall_duration)


if __name__ == "__main__":
    anyio.run(main)
