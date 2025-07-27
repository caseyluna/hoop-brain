# infra/dagger/orchestrator.py

import time
from typing import Any, Dict, List, Optional

import anyio
from config import load_pipelines_config, load_services_config
from dotenv import dotenv_values
from service import Service
from utils import (
    check_passed,
    pretty_print,
    status_emoji,
    validate_pipelines_config,
    validate_services_config,
)


class DaggerOrchestrator:
    def __init__(self, client, db_url: Optional[str] = None):
        self.client = client
        self.db_url = db_url
        self.env = dotenv_values(".env.test")
        self.services_config: Dict[str, Any] = load_services_config()
        self.pipelines_config: Dict[str, Any] = load_pipelines_config()
        # validate configs
        validate_services_config(self.services_config)
        validate_pipelines_config(self.pipelines_config, self.services_config)

    def set_env_vars(self, container):
        for key, value in self.env.items():
            container = container.with_env_variable(key, value)
        return container

    def _get_service(self, name: str) -> Service:
        conf = self.services_config.get(name)
        if conf is None:
            raise ValueError(f"Service '{name}' is not defined in the configuration.")
        return Service(
            self.client,
            name,
            conf,
            all_services_config=self.services_config,
            db_url=self.db_url,
        )

    async def run_check(self, service_name: str, check: str) -> Dict[str, Any]:
        service = self._get_service(service_name)
        container = service.get_container_with_deps()
        command = service.get_command(check)
        start = time.perf_counter()
        result = await container.with_exec(command).stdout()
        elapsed = time.perf_counter() - start
        await pretty_print(service_name, check, result)
        passed = check_passed(result)
        return {
            "service": service_name,
            "check": check,
            "status": status_emoji(passed),
            "elapsed": elapsed,
        }

    async def run_job(
        self, service_name: str, job: str, job_args: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        service = self._get_service(service_name)
        container = service.get_container_with_deps()
        command = service.get_job_command(job)
        if isinstance(command, str):
            command = [command]
        if job_args is None:
            command += job_args or []
        start = time.perf_counter()
        result = await container.with_exec(command).stdout()
        elapsed = time.perf_counter() - start
        await pretty_print(service_name, job, result)
        passed = check_passed(result)
        return {
            "service": service_name,
            "job": job,
            "status": status_emoji(passed),
            "elapsed": elapsed,
        }

    async def _run_and_collect(self, idx, coro, args, results):
        res = await coro(*args)
        results[idx] = res

    async def run_in_parallel(self, tasks):
        """
        tasks: list of (coroutine, args)
        Runs all tasks in parallel, preserves order.
        """
        results = [None] * len(tasks)
        async with anyio.create_task_group() as tg:
            for idx, (coro, args) in enumerate(tasks):
                tg.start_soon(self._run_and_collect, idx, coro, args, results)
        return results

    async def run_all_checks_for_service(
        self, service_name: str
    ) -> List[Dict[str, Any]]:
        service = self._get_service(service_name)
        checks = service.available_checks()
        tasks = [(self.run_check, (service_name, check)) for check in checks]
        return await self.run_in_parallel(tasks)

    async def run_all_checks_for_services_parallel(
        self, services: List[str]
    ) -> List[Dict[str, Any]]:
        tasks = [
            (self.run_all_checks_for_service, (service_name,))
            for service_name in services
        ]
        # This will return a list of lists, so flatten:
        results = await self.run_in_parallel(tasks)
        return [item for sublist in results for item in (sublist or [])]

    async def run_all_checks_for_services_sequential(
        self, services: List[str]
    ) -> List[Dict[str, Any]]:
        results = []
        for service_name in services:
            results.extend(await self.run_all_checks_for_service(service_name))
        return results

    async def run_jobs_for_services_parallel(self, jobs):
        """
        jobs: list of (service_name, job_name)
        Runs all jobs in parallel, preserves order.
        """
        tasks = [(self.run_job, (service, job)) for service, job in jobs]
        return await self.run_in_parallel(tasks)

    async def run_jobs_for_services_sequential(self, jobs):
        """
        jobs: list of (service_name, job_name)
        Runs all jobs sequentially, in order.
        """
        results = []
        for service, job in jobs:
            res = await self.run_job(service, job)
            results.append(res)
        return results

    def _action_task(self, service: str, action: str):
        """
        Returns (coroutine, args) tuple for running a check or job
        """
        svc = self._get_service(service)
        if action in svc.available_checks():
            return (self.run_check, (service, action))
        elif action in svc.available_jobs():
            return (self.run_job, (service, action, []))
        else:
            raise ValueError(
                f"Action '{action}' is not available for service '{service}'"
            )

    async def run_pipeline(self, pipeline_name):
        pipeline = self.pipelines_config.get(pipeline_name)
        if not pipeline:
            raise ValueError(
                f"Pipeline '{pipeline_name}' is not defined in the configuration."
            )

        # If pipeline is just a list of services, run all checks for each service
        if "services" in pipeline:
            services = pipeline["services"]
            order = pipeline.get("order", "parallel")
            if order == "parallel":
                return await self.run_all_checks_for_services_parallel(services)
            else:
                return await self.run_all_checks_for_services_sequential(services)

        # If pipeline is a list of steps (service: [actions]), run those
        elif "steps" in pipeline:
            steps = pipeline["steps"]
            order = pipeline.get("order", "sequential")
            results = []
            if order == "parallel":
                tasks = []
                for step in steps:
                    if isinstance(step, dict):
                        for service, actions in step.items():
                            for action in actions:
                                tasks.append(self._action_task(service, action))
                    else:
                        raise ValueError(f"Pipeline step '{step}' is not a valid dict")
                results = await self.run_in_parallel(tasks)
            else:
                for step in steps:
                    tasks = []
                    if isinstance(step, dict):
                        for service, actions in step.items():
                            for action in actions:
                                tasks.append(self._action_task(service, action))
                    else:
                        raise ValueError(f"Pipeline step '{step}' is not a valid dict")
                    step_results = await self.run_in_parallel(tasks)
                    results.extend(step_results)
            return results
        else:
            raise ValueError(f"Invalid pipeline definition for '{pipeline_name}'")

    async def run_integration_test(self):
        """
        Run integration tests with a persistent database connection.
        """
        user = self.env.get("POSTGRES_USER", "postgres")
        db_name = self.env.get("POSTGRES_DB", "hoopbrain_test")
        password = self.env.get("POSTGRES_PASSWORD", "postgres")
        db_url = f"postgresql://{user}:{password}@db:5432/{db_name}"

        # create database container
        db = (
            self.client.container()
            .build(
                context=self.client.host().directory("db/postgres"),
            )
            .with_env_variable("POSTGRES_DB", db_name)
            .with_env_variable("POSTGRES_USER", user)
            .with_env_variable("POSTGRES_PASSWORD", password)
            .with_exposed_port(5432)
            .as_service()
        )
        # create migrations container
        migrate_container = (
            self.client.container()
            .build(context=self.client.host().directory("api"))
            .with_service_binding("db", db)
            .with_mounted_directory(
                "/app/alembic",
                self.client.host().directory("api/alembic"),
            )
        )
        migrate_container = self.set_env_vars(migrate_container).with_env_variable(
            "DATABASE_URL", db_url
        )
        migration_cmd = (
            f"./scripts/wait-for-db.sh db psql -h db -U {user} -c 'CREATE DATABASE {db_name}' || true && "
            f"./scripts/wait-for-db.sh db uv run alembic upgrade head"
        )
        output = await migrate_container.with_exec(
            ["bash", "-c", migration_cmd]
        ).stdout()
        print("--- Alembic Migration Output ---\n", output)
        await migrate_container.with_exec(
            ["bash", "-c", "psql -h db -U postgres -d hoopbrain_test -c '\\dt'"]
        ).stdout()

        # run sync engine to populate the database
        sync_container = (
            self.client.container()
            .build(context=self.client.host().directory("pipelines/sync-engine"))
            .with_service_binding("db", db)
        )
        sync_container = self.set_env_vars(sync_container).with_env_variable(
            "DATABASE_URL", db_url
        )
        await sync_container.with_exec(["uv", "run", "python", "src/main.py"]).stdout()

        # run api integration tests
        api_test_container = (
            self.client.container()
            .build(context=self.client.host().directory("api"))
            .with_service_binding("db", db)
            .with_mounted_directory(
                "/app/alembic",
                self.client.host().directory("api/alembic"),
            )
        )
        api_test_container = self.set_env_vars(api_test_container).with_env_variable(
            "DATABASE_URL", db_url
        )
        test_output = await api_test_container.with_exec(
            ["uv", "run", "pytest", "tests"]
        ).stdout()
        print(test_output)
