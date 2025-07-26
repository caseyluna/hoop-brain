import asyncio
import sys
import time
from typing import List

import dagger
from ci_pipeline import CIPipeline
from utils import console, print_ci_summary


async def main() -> None:
    args: List[str] = sys.argv[1:]
    action: str = args[0] if args else "all-checks"
    services: List[str] = [arg for arg in args[1:] if not arg.startswith("--")]

    # Default services if none provided
    if not services:
        services = ["ingestion-engine", "model-engine", "transformation-engine"]

    async with dagger.Connection() as client:
        ci = CIPipeline(client, services)
        await ci.setup_services()

        overall_start = time.perf_counter()

        if action == "all-checks":
            # Run all services (sequential) with their checks (parallel)
            results = await ci.run_all_services_sequentially()
        else:
            # Run only the specified check for each service
            results = []
            for service in services:
                console.rule(
                    f"[bold blue]▶ {service.upper()} | {action.upper()}[/bold blue]"
                )
                res = await ci.run_check(service, action)
                results.append(res)

        overall_duration = time.perf_counter() - overall_start

        # Print summary from utils
        print_ci_summary(results, overall_duration)


if __name__ == "__main__":
    asyncio.run(main())
