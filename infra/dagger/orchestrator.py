# infra/dagger/orchestrator.py

import anyio
from config import load_pipelines_config, load_services_config
from services.generic_service import GenericService
from utils import check_passed, pretty_print


class DaggerOrchestrator:
    def __init__(self, client, db_url=None):
        self.client = client
        self.db_url = db_url
        self.services_config = load_services_config()
        self.pipelines_config = load_pipelines_config()

    def _get_service(self, name):
        conf = self.services_config[name]
        return GenericService(self.client, name, conf, db_url=self.db_url)

    async def run_check(self, service_name, check):
        service = self._get_service(service_name)
        if service.type == "fastapi" and check == "test":
            container = await service.get_test_container_with_deps()
        else:
            container = service.get_container()
        command = service.get_command(check)
        result = await container.with_exec(command).stdout()
        await pretty_print(service_name, check, result)
        passed = check_passed(result)
        return {
            "service": service_name,
            "check": check,
            "status": "✅ PASSED" if passed else "❌ FAILED",
            "elapsed": 0,
        }

    async def run_job(self, service_name, job, job_args=None):
        service = self._get_service(service_name)
        container = service.get_container()
        command = service.get_job_command(job)

        # Ensure it's a list before appending
        if isinstance(command, str):
            command = [command]

        if job_args:
            command += job_args

        result = await container.with_exec(command).stdout()
        await pretty_print(service_name, job, result)
        passed = check_passed(result)
        return {
            "service": service_name,
            "job": job,
            "status": "✅ PASSED" if passed else "❌ FAILED",
            "elapsed": 0,
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

    async def run_all_checks_for_service(self, service_name):
        service = self._get_service(service_name)
        checks = service.available_checks()
        tasks = [(self.run_check, (service_name, check)) for check in checks]
        return await self.run_in_parallel(tasks)

    async def run_all_checks_for_services_parallel(self, services):
        tasks = [
            (self.run_all_checks_for_service, (service_name,))
            for service_name in services
        ]
        # This will return a list of lists, so flatten:
        results = await self.run_in_parallel(tasks)
        return [item for sublist in results for item in sublist]

    async def run_all_checks_for_services_sequential(self, services):
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

    async def run_pipeline(self, pipeline_name):
        pipeline = self.pipelines_config[pipeline_name]
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
                    for service, actions in step.items():
                        for action in actions:
                            if action in self._get_service(service).available_checks():
                                tasks.append((self.run_check, (service, action)))
                            elif action in self._get_service(service).available_jobs():
                                tasks.append((self.run_job, (service, action)))
                results = await self.run_in_parallel(tasks)
            else:
                for step in steps:
                    tasks = []
                    for service, actions in step.items():
                        for action in actions:
                            if action in self._get_service(service).available_checks():
                                tasks.append((self.run_check, (service, action)))
                            elif action in self._get_service(service).available_jobs():
                                tasks.append((self.run_job, (service, action)))
                    step_results = await self.run_in_parallel(tasks)
                    results.extend(step_results)
            return results
        else:
            raise ValueError(f"Invalid pipeline definition for '{pipeline_name}'")
