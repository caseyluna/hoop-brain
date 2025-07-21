import re
from typing import Any, Dict, List

from rich.console import Console
from rich.panel import Panel

console = Console()


async def pretty_print(service: str, check: str, content: str) -> None:
    """
    Pretty print the output of a check with rich panels.
    """
    header = f"[bold yellow]{check.upper()}[/]"
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
            # dbt parse success fallback
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


def print_ci_summary(results: List[Dict[str, Any]], total_time: float) -> None:
    """
    Print a summary of all CI checks.
    """
    console.rule("[bold magenta]CI Summary[/bold magenta]")
    for r in results:
        console.print(
            f"[cyan]{r['service']}[/] | [yellow]{r['check']}[/]: {r['status']} "
            f"⏱ {r['elapsed']:.2f}s"
        )
    console.print(f"\n🔥 Total CI time: {total_time:.2f}s\n")
