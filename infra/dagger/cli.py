import sys
import time

import anyio
import dagger
from orchestrator import DaggerOrchestrator
from utils import print_ci_summary


async def main():
    args = sys.argv[1:]
    action = args[0] if args else "ci-all"
    # For jobs/checks: python cli.py job ingestion-engine run-main sync-engine sync-to-bq
    # For checks:      python cli.py check ingestion-engine lint
    # For pipeline:    python cli.py ci-all

    async with dagger.Connection() as client:
        orch = DaggerOrchestrator(client)
        overall_start = time.perf_counter()

        if action in orch.pipelines_config:
            # Run a pipeline as defined in pipelines.yaml
            results = await orch.run_pipeline(action)
        elif action == "check":
            # python cli.py check ingestion-engine lint
            results = [await orch.run_check(args[1], args[2])]
        elif action == "job":
            # python cli.py job ingestion-engine run-main
            # or python cli.py job ingestion-engine run-main sync-engine sync-to-bq
            jobs = []
            for i in range(1, len(args), 2):
                jobs.append((args[i], args[i + 1]))
            if len(jobs) == 1:
                results = [await orch.run_job(*jobs[0])]
            else:
                results = await orch.run_jobs_for_services_parallel(jobs)
        elif action == "all-checks-for-service":
            # python cli.py all-checks-for-service ingestion-engine
            results = await orch.run_all_checks_for_service(args[1])
        elif action == "all-checks":
            # python cli.py all-checks ingestion-engine sync-engine
            services = args[1:] if len(args) > 1 else list(orch.services_config.keys())
            results = await orch.run_all_checks_for_services_parallel(services)
        else:
            print("Unknown action")
            return

        overall_duration = time.perf_counter() - overall_start
        print_ci_summary(results, overall_duration)


if __name__ == "__main__":
    anyio.run(main)
