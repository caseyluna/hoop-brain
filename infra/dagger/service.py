import os
from typing import Any, Dict, Optional

import dagger


class Service:
    def __init__(
        self,
        client: dagger.Client,
        name: str,
        conf: dict,
        all_services_config: Optional[Dict[str, Any]],
        db_url: Optional[str] = None,
    ):
        self.client = client
        self.name = name
        self.conf = conf
        self.db_url = db_url
        self.type = conf["type"]
        self.src_dir = conf["src_dir"]
        self.checks = conf.get("checks", {})
        self.jobs = conf.get("jobs", {})
        self.dependencies = conf.get("dependencies", [])
        self.all_services_config = all_services_config

    def get_container(self):
        # build a Dagger container for the service based on its Dockerfile
        return self.client.container().build(
            context=self.client.host().directory(self.src_dir),
            dockerfile="Dockerfile",
        )

    def get_container_with_deps(self):
        """
        Recursively build and bind all declared deps as a Dagger service
        """
        container = self.get_container()

        # handle gcp service account key
        key_path = os.path.abspath("keys/service_account.json")
        key_in_container = "/app/keys/service_account.json"
        if os.path.exists(key_path):
            container = container.with_mounted_file(
                key_in_container, self.client.host().file(key_path)
            ).with_env_variable("GOOGLE_APPLICATION_CREDENTIALS", key_in_container)
        else:
            container = container.with_env_variable(
                "GOOGLE_APPLICATION_CREDENTIALS", ""
            )

        # handle dependencies
        for dep_name in self.dependencies:
            dep_conf = self.all_services_config.get(dep_name)
            if dep_conf is None:
                raise ValueError(
                    f"Dependency '{dep_name}' for service '{self.name}' is not defined in the configuration."
                )
            dep_service = Service(
                self.client,
                dep_name,
                dep_conf,
                self.all_services_config,
                self.db_url,
            )
            dep_container = dep_service.get_container_with_deps()
            container = container.with_service_binding(
                dep_name, dep_container.as_service()
            )
        if "db" in self.dependencies and self.db_url:
            container = container.with_env_variable("DATABASE_URL", self.db_url)
        print(
            f"Service: {self.name}, Dependencies: {self.dependencies}, DB URL: {self.db_url}"
        )
        return container

    def available_checks(self):
        # return the available checks for this service
        return list(self.checks.keys())

    def get_command(self, check):
        # return the command to run a specific check
        if check not in self.checks:
            raise ValueError(
                f"Check '{check}' is not available for service '{self.name}'"
            )
        return self.checks[check]

    def available_jobs(self):
        # return the available jobs for this service
        return list(self.jobs.keys())

    def get_job_command(self, job):
        # return the command to run a specific job
        if job not in self.jobs:
            raise ValueError(f"Job '{job}' is not available for service '{self.name}'")
        return self.jobs[job]
