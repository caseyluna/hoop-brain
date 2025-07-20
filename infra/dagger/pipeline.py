import asyncio
import sys
import time

import dagger
from rich.console import Console
from rich.panel import Panel

console = Console()

# === UTILS ===


async def pretty_print(service, check, content):
    header = f"[bold cyan]{service.upper()}[/] | [bold yellow]{check.upper()}[/]"
    panel = Panel.fit(content.strip(), title=header, border_style="green")
    console.print(panel)


def check_passed(output):
    # Naive pass/fail detector (customize as needed)
    if "error" in output.lower() or "failed" in output.lower():
        return False
    return True


# === ACTION FUNCTIONS ===


async def run_check(ctr, service, check, command):
    result = await ctr.with_exec(command).stdout()
    await pretty_print(service, check, result)
    status = "✅ PASSED" if check_passed(result) else "❌ FAILED"
    return {"service": service, "check": check, "status": status}


async def run_all_checks(ctr, service):
    tasks = [
        run_check(
            ctr, service, "lint", ["uv", "run", "ruff", "format", "--check", "."]
        ),
        run_check(ctr, service, "typecheck", ["uv", "run", "ruff", "check", "."]),
        run_check(ctr, service, "test", ["uv", "run", "pytest", "tests"]),
        run_check(
            ctr,
            service,
            "coverage",
            ["uv", "run", "pytest", "--cov=src", "--cov-report=term-missing", "tests"],
        ),
    ]
    return await asyncio.gather(*tasks)


# === MAIN ENTRY POINT ===


async def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "all-checks"
    service = sys.argv[2] if len(sys.argv) > 2 else "ingestion-engine"
    force_rebuild = "--force-rebuild" in sys.argv

    base_path = "backend"
    service_path = f"{base_path}/{service}"

    async with dagger.Connection() as client:
        build = client.container().build(
            context=client.host().directory(service_path),
            dockerfile="Dockerfile",
        )

        if force_rebuild:
            build = build.with_env_variable("CACHE_BUST", str(time.time()))

        ctr = build.with_mounted_directory(
            "/app", client.host().directory(service_path)
        ).with_workdir("/app")

        actions = {
            "lint": lambda c: run_check(
                c, service, "lint", ["uv", "run", "ruff", "format", "--check", "."]
            ),
            "typecheck": lambda c: run_check(
                c, service, "typecheck", ["uv", "run", "ruff", "check", "."]
            ),
            "test": lambda c: run_check(
                c, service, "test", ["uv", "run", "pytest", "tests"]
            ),
            "coverage": lambda c: run_check(
                c,
                service,
                "coverage",
                [
                    "uv",
                    "run",
                    "pytest",
                    "--cov=src",
                    "--cov-report=term-missing",
                    "tests",
                ],
            ),
            "all-checks": lambda c: run_all_checks(c, service),
        }

        if action not in actions:
            raise ValueError(
                f"Unknown action: {action}. Choose from: {', '.join(actions.keys())}"
            )

        results = await actions[action](ctr)

        # Collect and print summary
        summary = results if isinstance(results, list) else [results]
        console.rule("[bold magenta]Summary[/bold magenta]")
        for item in summary:
            console.print(
                f"[cyan]{item['service']}[/] | [yellow]{item['check']}[/]: {item['status']}"
            )


if __name__ == "__main__":
    asyncio.run(main())
