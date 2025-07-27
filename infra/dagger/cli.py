import argparse
import os
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


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


# Load service and pipeline configurations
SERVICES = load_yaml("services.yaml")["services"]
PIPELINES = load_yaml("pipelines.yaml")["pipelines"]


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Dagger CLI")
    parser.add_argument("--env", choices=["test", "prod"], default="test")
    sub = parser.add_subparsers(dest="command", required=True)

    for pipe in PIPELINES:
        sub.add_parser(pipe, help=f"Run pipeline: {pipe}")
    job = sub.add_parser("job", help="Run a single job for a service")
    job.add_argument("service", choices=SERVICES.keys())
    job.add_argument("job", help="Job name to run")
    return parser


async def start_db_service(client, db_url):
    conf = SERVICES["db"]
    c = client.container().build(
        context=client.host().directory(conf["src_dir"]),
        dockerfile=conf.get("dockerfile", "Dockerfile"),
    )
    c = (
        c.with_env_variable("POSTGRES_DB", db_url.rsplit("/", 1)[-1])
        .with_env_variable("POSTGRES_USER", "postgres")
        .with_env_variable("POSTGRES_PASSWORD", "postgres")
        .with_exposed_port(5432)
        .as_service()
    )
    return c


async def run_job(client, service, job, db_url=None, db_service=None, sa_secret=None):
    conf = SERVICES[service]
    container = client.container().build(
        context=client.host().directory(conf["src_dir"]),
        dockerfile=conf.get("dockerfile", "Dockerfile"),
    )
    # Inject credentials via secret and write them in-container
    if sa_secret:
        container = container.with_secret_variable("GCP_SA_JSON", sa_secret)

        # 3) Write it into /app/keys/service_account.json inside the container
        container = container.with_exec(
            [
                "bash",
                "-lc",
                "mkdir -p /app/keys && "
                + "printf '%s' \"$GCP_SA_JSON\" > /app/keys/service_account.json",
            ]
        )

        # 4) Point SDKs at it
        container = container.with_env_variable(
            "GOOGLE_APPLICATION_CREDENTIALS", "/app/keys/service_account.json"
        )
    # Mount DBT profiles
    if service == "transformation-engine":
        profiles_dir = os.path.join(conf["src_dir"], "profiles")
        container = container.with_mounted_directory(
            "/app/profiles", client.host().directory(profiles_dir)
        )
    # Set DB URL
    if db_url:
        container = container.with_env_variable("DATABASE_URL", db_url)
    # Bind DB service
    if db_service and "db" in conf.get("dependencies", []):
        container = container.with_service_binding("db", db_service)
    # Execute job
    cmd = conf["jobs"][job]
    start = time.perf_counter()
    result = await container.with_exec(cmd).stdout()
    elapsed = time.perf_counter() - start
    await pretty_print(service, job, result)
    passed = check_passed(result)
    return {
        "service": service,
        "job": job,
        "status": status_emoji(passed),
        "elapsed": elapsed,
    }


async def run_pipeline(client, pipeline, db_url=None, sa_secret=None):
    steps = PIPELINES[pipeline]["steps"]
    results = []
    db_service = None
    # Start DB service if needed
    if any("db" in SERVICES[s].get("dependencies", []) for st in steps for s in st):
        db_service = await start_db_service(client, db_url)
    # Run each step
    for step in steps:
        for service, jobs in step.items():
            for job in jobs:
                res = await run_job(client, service, job, db_url, db_service, sa_secret)
                results.append(res)
    return results


async def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    db_url = (
        "postgresql://postgres:postgres@db:5432/hoopbrain"
        if args.env == "prod"
        else "postgresql://postgres:postgres@db:5432/hoopbrain_test"
    )
    # Load JSON from workspace
    sa_json = open("keys/service_account.json").read()
    async with dagger.Connection() as client:
        sa_secret = client.set_secret("GCP_SA", sa_json)
        start = time.perf_counter()
        if args.command == "job":
            results = [
                await run_job(client, args.service, args.job, db_url, None, sa_secret)
            ]
        else:
            results = await run_pipeline(client, args.command, db_url, sa_secret)
        duration = time.perf_counter() - start
        summary = flatten_results(results)
        print_summary(summary, duration)


if __name__ == "__main__":
    anyio.run(main)
