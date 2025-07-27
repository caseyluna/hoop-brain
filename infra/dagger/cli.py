import sys
import time

import anyio
import dagger
from orchestrator import DaggerOrchestrator
from utils import print_ci_summary


async def main():
    args = sys.argv[1:]
    # Default to "test" environment
    env = "test"
    if "--env" in args:
        env_index = args.index("--env")
        if env_index + 1 < len(args):
            env = args[env_index + 1]
            # Remove the flag and value from args so they don't interfere with other parsing
            args = args[:env_index] + args[env_index + 2 :]

    # Set the DB URL based on the environment
    if env == "prod":
        db_url = "postgresql://postgres:postgres@db:5432/hoopbrain_prod"
    else:
        db_url = "postgresql://postgres:postgres@db:5432/hoopbrain_test"

    action = args[0] if args else "ci-all"

    async with dagger.Connection() as client:
        orch = DaggerOrchestrator(client, db_url=db_url)
        overall_start = time.perf_counter()

        if action in orch.pipelines_config:
            # Run a pipeline as defined in pipelines.yaml
            results = await orch.run_pipeline(action)
        elif action == "check":
            if len(args) < 3:
                print("Usage: python cli.py check <service> <check>")
                return
            results = [await orch.run_check(args[1], args[2])]
        elif action == "job":
            # python cli.py job api alembic-revision "add teams table"
            if len(args) < 3:
                print("Usage: python cli.py job <service> <job> [<job_args>...]")
                return

            service = args[1]
            job = args[2]
            job_args = args[3:]  # everything after service + job

            results = [await orch.run_job(service, job, job_args)]
        elif action == "all-checks-for-service":
            # python cli.py all-checks-for-service ingestion-engine
            results = await orch.run_all_checks_for_service(args[1])
        elif action == "all-checks":
            # python cli.py all-checks ingestion-engine sync-engine
            services = args[1:] if len(args) > 1 else list(orch.services_config.keys())
            results = await orch.run_all_checks_for_services_parallel(services)
        else:
            print(
                f"Unknown action: '{action}'. Try one of: check, job, all-checks, all-checks-for-service, or a pipeline name from pipelines.yaml"
            )
            return

        overall_duration = time.perf_counter() - overall_start
        print_ci_summary(results, overall_duration)


if __name__ == "__main__":
    anyio.run(main)
