import asyncio
import time
from typing import Any, Dict, List

import dagger
from utils import check_passed, console, pretty_print


class CIPipeline:
    """
    Modular CI pipeline to run code checks across services.
    Supports Python and DBT services

    Args:
        client: Dagger client instance
        services: List of service names (e.g., ['ingestion-engine'])
    """

    def __init__(
        self,
        client: dagger.Client,
        services: List[str],
    ):
        self.client = client
        self.services = services
        self.containers: Dict[str, Any] = {}

    async def setup_services(self) -> None:
        """
        Prepare Dagger containers for each service
        """
        for service in self.services:
            service_path = f"pipelines/{service}"
            container = self.client.container().build(
                context=self.client.host().directory(service_path),
                dockerfile="Dockerfile",
            )

            self.containers[service] = container

    def get_checks_for_service(self, service: str) -> List[str]:
        """
        Get checks available for a given service
        """
        if service == "transformation-engine":
            # dbt based service
            return ["dbt-parse", "dbt-deps", "dbt-test", "dbt-build"]
        elif service in ("ingestion-engine", "model-engine"):
            # python based service
            return ["lint", "typecheck", "test", "coverage"]
        else:
            raise ValueError(f"Unknown service: {service}")

    def get_command_for_check(self, service: str, check: str) -> List[str]:
        """
        Get command to run a specific check for a service
        """
        if service == "transformation-engine":
            # dbt based service
            return {
                "dbt-parse": ["dbt", "parse", "--profiles-dir", "/app/profiles"],
                "dbt-deps": ["dbt", "deps", "--profiles-dir", "/app/profiles"],
                "dbt-test": ["dbt", "test", "--profiles-dir", "/app/profiles"],
                "dbt-build": ["dbt", "build", "--profiles-dir", "/app/profiles"],
            }[check]
        elif service in ("ingestion-engine", "model-engine"):
            # python based service
            return {
                "lint": ["uv", "run", "ruff", "format", "--check", "."],
                "typecheck": ["uv", "run", "ruff", "check", "."],
                "test": ["uv", "run", "pytest", "tests"],
                "coverage": [
                    "uv",
                    "run",
                    "pytest",
                    "--cov=ingestion_engine",
                    "--cov-report=html:coverage.html",
                    "tests",
                ],
            }[check]
        else:
            raise ValueError(f"Unknown service: {service} or check: {check}")

    async def run_check(self, service: str, check: str) -> Dict[str, Any]:
        """
        Run a single check on one service and capture result

        Args:
            service: Name of service to run check on
            check: Name of check to run
        Returns:
            Dict with service, check, duration, result
        """
        command = self.get_command_for_check(service, check)
        container = self.containers[service]

        start_time = time.perf_counter()
        result = await container.with_exec(command).stdout()
        elapsed = time.perf_counter() - start_time

        await pretty_print(service, check, result)

        passed = check_passed(result)
        status = "✅ PASSED" if passed else "❌ FAILED"

        return {
            "service": service,
            "check": check,
            "status": status,
            "elapsed": elapsed,
        }

    async def run_all_checks_for_service(self, service: str) -> List[Dict[str, Any]]:
        """
        Run all checks in parallel for one service

        Args:
            service: Name of service to run checks on

        Returns:
            List of all check results for the service
        """
        # dynamically get the list of checks for the service
        checks = self.get_checks_for_service(service)

        # create a list of tasks, one per check
        tasks = [self.run_check(service, check) for check in checks]

        # run all tasks in parallel and gather results
        return await asyncio.gather(*tasks)

    async def run_all_services_sequentially(self) -> List[Dict[str, Any]]:
        """
        Run all checks in parallel for all services sequentially
        """
        all_results = []
        for service in self.services:
            console.rule(f"[bold blue]▶ SERVICE: {service.upper()}[/bold blue]")
            results = await self.run_all_checks_for_service(service)
            all_results.extend(results)
        return all_results
