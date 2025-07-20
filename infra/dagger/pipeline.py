import asyncio
import os
import sys
import time

import dagger

# === ACTION FUNCTIONS ===


async def run_lint(ctr):
    result = await ctr.with_exec(
        ["uv", "run", "ruff", "format", "--check", "."]
    ).stdout()
    print("--- LINT ---\n", result)
    return result


async def run_typecheck(ctr):
    result = await ctr.with_exec(["uv", "run", "ruff", "check", "."]).stdout()
    print("--- TYPECHECK ---\n", result)
    return result


async def run_test(ctr):
    result = await ctr.with_exec(["uv", "run", "pytest", "tests"]).stdout()
    print("--- TESTS ---\n", result)
    return result


async def run_coverage(ctr):
    result = await ctr.with_exec(
        ["uv", "run", "pytest", "--cov=src", "--cov-report=term-missing", "tests"]
    ).stdout()
    print("--- COVERAGE ---\n", result)
    return result


async def run_all_checks(ctr):
    results = await asyncio.gather(
        run_lint(ctr),
        run_typecheck(ctr),
        run_test(ctr),
        run_coverage(ctr),
    )
    return results


# === MAIN ENTRY POINT ===


async def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "all"
    service = sys.argv[2] if len(sys.argv) > 2 else "ingestion-engine"
    force_rebuild = "--force-rebuild" in sys.argv

    # Set project root relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # go up two levels: infra/dagger -> infra/ -> hoop-brain/
    project_root = os.path.abspath(os.path.join(script_dir, "../.."))

    # build service path relative to project root
    base_path = os.path.join(project_root, "backend")
    service_path = os.path.join(base_path, service)

    print("Project root:", project_root)
    print("Service path:", service_path)

    async with dagger.Connection() as client:
        build_args = (
            [dagger.BuildArg(name="CACHEBUSTER", value=str(time.time()))]
            if force_rebuild
            else []
        )
        print("Build args: ", build_args)
        build = client.container().build(
            context=client.host().directory(service_path),
            dockerfile="Dockerfile",
            build_args=build_args,
        )

        ctr = build.with_mounted_directory(
            "/app", client.host().directory(service_path)
        ).with_workdir("/app")

        actions = {
            "lint": run_lint,
            "typecheck": run_typecheck,
            "test": run_test,
            "coverage": run_coverage,
            "all": run_all_checks,
        }

        if action not in actions:
            raise ValueError(
                f"Unknown action: {action}. Choose from: {', '.join(actions.keys())}"
            )

        await actions[action](ctr)


if __name__ == "__main__":
    asyncio.run(main())
