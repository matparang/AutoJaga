"""
Resource Guard — lightweight resource limits for agent subprocesses.

Applies ``resource.setrlimit`` caps on memory and CPU time before
subprocess execution, preventing runaway processes from consuming
all system resources.
"""

from __future__ import annotations

import os
import resource
from typing import Callable

from loguru import logger

# Defaults
DEFAULT_MAX_MEMORY_MB = 256
DEFAULT_MAX_CPU_SECONDS = 30


def make_preexec(
    max_memory_mb: int = DEFAULT_MAX_MEMORY_MB,
    max_cpu_seconds: int = DEFAULT_MAX_CPU_SECONDS,
) -> Callable[[], None]:
    """
    Return a preexec_fn that sets resource limits on the child process.

    Intended for use with ``subprocess.Popen(preexec_fn=...)``.
    """
    max_bytes = max_memory_mb * 1024 * 1024

    def _apply_limits() -> None:
        try:
            # Virtual memory limit
            resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
        except (ValueError, OSError):
            # RLIMIT_AS not supported on some platforms
            pass

        try:
            # CPU time limit (seconds)
            resource.setrlimit(resource.RLIMIT_CPU, (max_cpu_seconds, max_cpu_seconds + 5))
        except (ValueError, OSError):
            pass

    return _apply_limits


class ResourceGuard:
    """
    Manages resource limits for tool execution.

    Provides preexec functions for subprocess calls and tracks
    resource usage warnings.
    """

    def __init__(
        self,
        max_memory_mb: int = DEFAULT_MAX_MEMORY_MB,
        max_cpu_seconds: int = DEFAULT_MAX_CPU_SECONDS,
    ) -> None:
        self.max_memory_mb = max_memory_mb
        self.max_cpu_seconds = max_cpu_seconds
        self._warnings: list[str] = []

    @property
    def preexec_fn(self) -> Callable[[], None]:
        """Get preexec function for subprocess calls."""
        return make_preexec(self.max_memory_mb, self.max_cpu_seconds)

    def check_system_resources(self) -> dict[str, float]:
        """Check current system resource usage (informational)."""
        try:
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            return {
                "user_time_s": usage.ru_utime,
                "system_time_s": usage.ru_stime,
                "max_rss_kb": usage.ru_maxrss,
            }
        except Exception:
            return {}

    @property
    def warnings(self) -> list[str]:
        """Return accumulated resource warnings."""
        return list(self._warnings)
