import functools
import os
import time
import tracemalloc
from typing import Any, Callable, Dict, Optional

import psutil

from core.logging_utils import get_logger, log

logger = get_logger(__name__)
process = psutil.Process(os.getpid())


class PerfTracker:
    """
    A class to track performance metrics like execution time and memory usage.

    Metrics:
        - Execution time in seconds
        - System emory usage in bytes
        - Peak memory usage in bytes

    Usage:
        with PerfTracker("my-task") as perf_tracker:
            ...
        @PerfTracker("my-task")
        def my_function():
            ...
    """

    def __init__(self, task_name: str, extra_tags: Optional[Dict[str, Any]] = None):
        self.task_name = task_name
        self.extra_tags = extra_tags or {}
        self.start_time: Optional[float] = None
        self.start_memory: Optional[int] = None
        self.peak_memory: Optional[int] = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        self.start_memory = process.memory_info().rss
        tracemalloc.start()
        log(
            logger,
            "INFO",
            f"⏱ Starting performance tracking for '{self.task_name}'",
            name="PerfTracker",
        )
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        elapsed = time.perf_counter() - (self.start_time or 0)
        current_memory = process.memory_info().rss
        self.peak_memory = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()

        delta_memory_mb = (current_memory - self.start_memory or 0) / (1024 * 1024)
        status = "OK" if exc_type is None else "FAILED ({exc_type.__name__})"

        log(
            logger,
            "SUCCESS" if status == "OK" else "ERROR",
            (
                f"{status} '{self.task_name}' | Time: {elapsed:.2f}s | "
                f"Peak Python Memory: {self.peak_memory / (1024 * 1024):.2f} MB | "
                f"Delta Memory: {delta_memory_mb:.2f} MB"
            ),
            name="PerfTracker",
        )

    @classmethod
    def decorator(cls, task_name: str, extra_tags: Optional[Dict[str, Any]] = None):
        """
        Decorator to use PerfTracker with functions.
        """

        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with cls(task_name, extra_tags):
                    return func(*args, **kwargs)

            return wrapper

        return decorator
