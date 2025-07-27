# infra/dagger/utils.py

import re
from typing import Any, Dict, List

from rich.console import Console
from rich.panel import Panel

console = Console()


def flatten_results(results):
    """
    Flattens a list of results that may contain nested lists or None
    Returns a flat list of non-None results.
    """
    if not results:
        return []
    flat = []
    for sub in results:
        if sub is None:
            continue
        if isinstance(sub, list):
            flat.extend(flatten_results(sub))
        else:
            flat.append(sub)
    return flat


def status_emoji(passed: bool) -> str:
    """
    Returns a status emoji based on whether the check passed or failed.
    return '✅ PASSED' if passed else '❌ FAILED'
    """
    return "✅ PASSED" if passed else "❌ FAILED"


async def pretty_print(service: str, action: str, content: str) -> None:
    """
    Pretty print the output of a check or job with rich panels.
    """
    header = f"[bold yellow]{action.upper()}[/]"
    panel = Panel.fit(content.strip(), title=header, border_style="green")
    console.print(panel)


def check_passed(output: str) -> bool:
    """
    Robust check pass/fail detector for dbt, pytest, ruff, etc.

    Args:
        output: CLI output string

    Returns:
        True if check passed, False if failed
    """
    lower_output = output.lower()

    # --- DBT-specific checks ---
    if "dbt" in lower_output:
        if "completed successfully" in lower_output:
            return True
        if "done. pass=" in lower_output:
            match = re.search(r"pass=(\d+).*error=(\d+)", lower_output)
            if match:
                errors = int(match.group(2))
                return errors == 0
        if "nothing to do" in lower_output:
            return True
        if "warning: no packages were found" in lower_output:
            return True
        if "performance info" in lower_output and "error" not in lower_output:
            return True
        return False

    # --- Pytest-specific checks ---
    if "pytest" in lower_output:
        if "failed" in lower_output:
            failed_match = re.search(r"(\d+)\s+failed", lower_output)
            if failed_match:
                failed_count = int(failed_match.group(1))
                return failed_count == 0
        return True

    # --- Ruff / lint / typecheck ---
    if "ruff" in lower_output:
        if "error" in lower_output or "failed" in lower_output:
            return False
        return True

    # --- General fallback ---
    if "error" in lower_output and "0 error" not in lower_output:
        return False
    if "failed" in lower_output and "0 failed" not in lower_output:
        return False

    return True


def print_summary(
    results: List[Dict[str, Any]], total_time: float, title: str = "Run Summary"
) -> None:
    """
    Print a summary of all checks, jobs, or other actions
    """
    console = Console()
    console.rule(f"[bold magenta]{title}[/bold magenta]")
    for r in results:
        # prefer 'check', then 'job', then fallback to any action key
        action = r.get("check") or r.get("job") or r.get("action") or "unknown"

        console.print(
            f"[cyan]{r.get('service', '?')}[/] | [yellow]{action}[/]: {r.get('status', '?')} "
            f"⏱ {r.get('elapsed', 0):.2f}s"
        )
    console.print(f"\n🔥 Total time: {total_time:.2f}s\n")


def validate_services_config(services_config):
    """
    Validates the structure of the services config.
    Raises ValueError if the config is invalid.
    """
    if not isinstance(services_config, dict):
        raise ValueError("Services config must be a dictionary.")
    for name, conf in services_config.items():
        if not isinstance(conf, dict):
            raise ValueError(f"Service '{name}' config must be a dictionary.")
        for field in ("type", "src_dir"):
            if field not in conf:
                raise ValueError(
                    f"Service '{name}' is missing required field '{field}'."
                )
        deps = conf.get("dependencies", [])
        if not isinstance(deps, list):
            raise ValueError(f"Service '{name}' dependencies must be a list.")
        for section in ("checks", "jobs"):
            val = conf.get(section, {})
            if not isinstance(val, dict):
                raise ValueError(f"Service '{name}' '{section}' must be a dictionary.")


def validate_pipelines_config(pipelines_config, services_config):
    """
    Validates the structure of the pipelines config.
    Raises ValueError if the config is invalid.
    """
    if not isinstance(pipelines_config, dict):
        raise ValueError("Pipelines config must be a dictionary.")
    for name, conf in pipelines_config.items():
        if not isinstance(conf, dict):
            raise ValueError(f"Pipeline '{name}' config must be a dictionary.")
        if "services" in conf:
            for svc in conf["services"]:
                if svc not in services_config:
                    raise ValueError(
                        f"Pipeline '{name}' references unknown service '{svc}'."
                    )
        if "steps" in conf:
            for step in conf["steps"]:
                if not isinstance(step, dict):
                    raise ValueError(f"Pipeline '{name}' step must be a dict.")
                for svc, actions in step.items():
                    if svc not in services_config:
                        raise ValueError(
                            f"Pipeline '{name}' step references unknown service '{svc}'."
                        )
                    if not isinstance(actions, list):
                        raise ValueError(
                            f"Pipeline '{name}' step actions for service '{svc}' must be a list."
                        )
