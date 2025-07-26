import dagger


class GenericService:
    def __init__(
        self, client: dagger.Client, name: str, conf: dict, no_cache: bool = False
    ):
        self.client = client
        self.name = name
        self.conf = conf
        self.type = conf["type"]
        self.src_dir = conf["src_dir"]
        self.checks = conf.get("checks", {})
        self.jobs = conf.get("jobs", {})

    def get_container(self):
        # build a Dagger container for the service based on its Dockerfile
        return self.client.container().build(
            context=self.client.host().directory(self.src_dir),
            dockerfile="Dockerfile",
        )

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

    def get_test_container_with_deps(self):
        # build a Dagger container with dependencies for integration testing
        return self.get_container()
