import logging
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

# create a global console instance for rich
console = Console()

# Predfined emojis + styles per log level
LOG_STYLES = {
    "DEBUG": ("🐛", "[dim cyan]"),
    "INFO": ("ℹ️", "[bold green]"),
    "SUCCESS": ("✅", "[bold green]"),
    "WARNING": ("⚠️", "[bold yellow]"),
    "ERROR": ("❌", "[bold red]"),
    "CRITICAL": ("🚨", "[bold red]"),
}


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Create a logger with rich console output

    Args:
        name(str): Name of the logger (usually __name__)
        level(int): Logging level (e.g. logging.DEBUG, logging.INFO)
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)

    # prevent adding multiple handlers if called multiple times
    if logger.hasHandlers():
        return logger

    # Setup rich handler
    rich_handler = RichHandler(
        console=console, show_time=True, show_level=True, show_path=True, markup=True
    )

    formatter = logging.Formatter("[%(name)s] %(message)s")

    rich_handler.setFormatter(formatter)
    logger.addHandler(rich_handler)
    logger.setLevel(level)

    return logger


def log(
    logger: logging.Logger, level: str, message: str, name: Optional[str] = None
) -> None:
    """
    Log a message with pre-defined log style

    Args:
        logger (logging.Logger): Logger instance from get_logger()
        level (str): Log level (DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL)
        message (str): Message to log
        name (Optional[str]): Optional short name (e.g. function or module) to include in the log message
    """

    emoji, style = LOG_STYLES.get(level.upper(), ("🔷", "[white]"))
    prefix = f"[bold magenta]{name}[/bold magenta]: " if name else ""
    full_message = f"{emoji} {style}{prefix}{message}[/]"

    if level.upper() == "DEBUG":
        logger.debug(full_message)
    elif level.upper() == "INFO":
        logger.info(full_message)
    elif level.upper() == "SUCCESS":
        logger.info(full_message)
    elif level.upper() == "WARNING":
        logger.warning(full_message)
    elif level.upper() == "ERROR":
        logger.error(full_message)
    elif level.upper() == "CRITICAL":
        logger.critical(full_message)
    else:
        logger.info(full_message)
