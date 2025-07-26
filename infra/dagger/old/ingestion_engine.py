import dagger
from utils import pretty_print


async def run_main_py(client: dagger.Client, service: str = "ingestion-engine") -> None:
    """
    Build the ingestion-engine container and run main.py inside.
    """
    service_path = f"pipelines/{service}"

    container = (
        client.container()
        .build(context=client.host().directory(service_path), dockerfile="Dockerfile")
        .with_mounted_file(
            "/app/keys/service_account.json",
            client.host().file("keys/service_account.json"),
        )
        .with_env_variable(
            "GOOGLE_APPLICATION_CREDENTIALS", "/app/keys/service_account.json"
        )
        .with_workdir("/app")
    )

    result = await container.with_exec(["uv", "run", "python", "src/main.py"]).stdout()
    await pretty_print(service, "main.py", result)
