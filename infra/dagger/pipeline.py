import asyncio
import sys

import dagger

module = sys.argv[1] if len(sys.argv) > 1 else "boxscore"


async def main():
    async with dagger.Connection() as client:
        # Base container + mount project code
        base = (
            client.container()
            .from_("python:3.10-slim")
            .with_mounted_directory("/src", client.host().directory("."))
            .with_workdir("/src/backend/ingestion-engine")
            # Cache pip installs (speeds up repeat runs)
            .with_mounted_cache("/root/.cache/pip", client.cache_volume("pip_cache"))
        )

        # Install requirements (only re-executes if requirements.txt changes)
        deps = base.with_exec(["pip", "install", "-r", "requirements.txt"])

        # Run app (reuses pip layer, only reruns if app or code changes)
        app = deps.with_exec(["python", "app.py", "--module", module])

        # Capture stdout + stderr
        stdout = await app.stdout()
        stderr = await app.stderr()

        print("--- STDOUT ---")
        print(stdout)
        print("--- STDERR ---")
        print(stderr)


if __name__ == "__main__":
    asyncio.run(main())
