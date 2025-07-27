# infra/dagger/cli.py

import argparse
import sys
import time

import anyio
import dagger
import yaml
from dotenv import dotenv_values
from utils import (
    check_passed,
    flatten_results,
    pretty_print,
    print_summary,
    status_emoji,
)


def load_yaml(filename):
    with open(filename) as f:
        return yaml.safe_load(f)


SERVICES = load_yaml("services.yaml")["services"]
PIPELINES = load_yaml("pipelines.yaml")["pipelines"]
ENV = dotenv_values(".env.test")


def set_env_vars(container):
    for key, value in ENV.items():
        container = container.with_env_variable(key, value)
    return container


async def start_db_service(client, db_url, db_service_name="db"):
    db_conf = SERVICES[db_service_name]
    dockerfile = db_conf.get("dockerfile", "Dockerfile")
    db_container = (
        client.container()
        .build(
            context=client.host().directory(db_conf["src_dir"]),
            dockerfile=dockerfile,
        )
        .with_env_variable("POSTGRES_DB", db_url.rsplit("/", 1)[-1])
        .with_env_variable("POSTGRES_USER", "postgres")
        .with_env_variable("POSTGRES_PASSWORD", "postgres")
        .with_exposed_port(5432)
        .as_service()
    )
    return db_container


async def run_job(client, service, job, db_url=None, db_service=None):
    conf = SERVICES[service]
    dockerfile = conf.get("dockerfile", "Dockerfile")
    container = (
        client.container()
        .build(
            context=client.host().directory(conf["src_dir"]),
            dockerfile=dockerfile,
        )
        .with_mounted_file(
            "/app/keys/service_account.json",
            client.host().file("keys/service_account.json"),
        )
    )
    container = set_env_vars(container)
    if db_url:
        container = container.with_env_variable("DATABASE_URL", db_url)
    if db_service and "db" in conf.get("dependencies", []):
        container = container.with_service_binding("db", db_service)
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


async def run_pipeline(client, pipeline, db_url=None):
    steps = PIPELINES[pipeline].get("steps", [])
    results = []
    db_service = None
    needs_db = any(
        "db" in SERVICES[svc].get("dependencies", []) for step in steps for svc in step
    )
    if needs_db:
        print("Starting persistent db")
        db_service = await start_db_service(client, db_url)
    for step in steps:
        for service, jobs in step.items():
            for job in jobs:
                res = await run_job(client, service, job, db_url, db_service)
                results.append(res)
    return results


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Dagger CLI")
    parser.add_argument("--env", choices=["test", "prod"], default="test")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for pipeline in PIPELINES:
        subparsers.add_parser(pipeline, help=f"Run pipeline: {pipeline}")

    job_parser = subparsers.add_parser("job", help="Run a job for a service")
    job_parser.add_argument("service", choices=SERVICES.keys())
    job_parser.add_argument("job", help="Job name to run")

    return parser


async def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    db_url = (
        "postgresql://postgres:postgres@db:5432/hoopbrain"
        if args.env == "prod"
        else "postgresql://postgres:postgres@db:5432/hoopbrain_test"
    )

    async with dagger.Connection() as client:
        overall_start = time.perf_counter()

        if args.command == "job":
            results = [await run_job(client, args.service, args.job, db_url)]
        elif args.command in PIPELINES:
            results = await run_pipeline(client, args.command, db_url)
        else:
            parser.print_help()
            sys.exit(1)

        overall_duration = time.perf_counter() - overall_start
        results = flatten_results(results)
        print_summary(results, overall_duration)


if __name__ == "__main__":
    anyio.run(main)
