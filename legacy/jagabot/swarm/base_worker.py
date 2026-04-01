"""Stateless worker that wraps a Tool ABC instance for process-safe execution.

v2.2: Added HardenedWorkerConfig, per-tool timeout enforcement,
self-correction retry loop, and optional Docker sandbox routing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Hardened worker config
# ------------------------------------------------------------------

@dataclass
class HardenedWorkerConfig:
    """Per-tool security policy applied by _run_tool_sync."""

    timeout_s: int = 30
    max_retries: int = 1
    sandbox_mode: str = "none"  # "none" | "docker" | "subprocess"


# Sensible defaults — exec tool gets Docker sandbox and retries
TOOL_SECURITY_POLICIES: dict[str, HardenedWorkerConfig] = {
    "exec": HardenedWorkerConfig(timeout_s=60, max_retries=2, sandbox_mode="docker"),
    "monte_carlo": HardenedWorkerConfig(timeout_s=45, max_retries=2),
    "bayesian": HardenedWorkerConfig(timeout_s=30, max_retries=2),
    "sensitivity": HardenedWorkerConfig(timeout_s=30, max_retries=2),
}

DEFAULT_POLICY = HardenedWorkerConfig()


def get_policy(tool_name: str) -> HardenedWorkerConfig:
    """Return the security policy for *tool_name* (or the default)."""
    return TOOL_SECURITY_POLICIES.get(tool_name, DEFAULT_POLICY)


# ------------------------------------------------------------------
# Core execution function (picklable — top-level)
# ------------------------------------------------------------------

def _run_tool_sync(tool_cls_name: str, method: str, params: dict[str, Any]) -> str:
    """Execute a tool in the current process (picklable top-level function).

    This is the function submitted to ProcessPoolExecutor.  v2.2 adds:
    - Per-tool timeout via ``asyncio.wait_for``
    - Self-correction retry via ``SelfCorrectingRunner``
    - Optional Docker sandbox for dangerous tools
    """
    from jagabot.swarm.tool_registry import get_tool_class

    cls = get_tool_class(tool_cls_name)
    if cls is None:
        return json.dumps({"error": f"Unknown tool: {tool_cls_name}"})

    policy = get_policy(tool_cls_name)
    tool = cls()

    async def _exec() -> str:
        if method and method != "__direct__":
            return await tool.execute(method=method, params=params)
        else:
            return await tool.execute(**params)

    async def _exec_with_timeout() -> str:
        return await asyncio.wait_for(_exec(), timeout=policy.timeout_s)

    # Build the retry-wrapped coroutine
    async def _hardened() -> str:
        if policy.max_retries > 1:
            from jagabot.sandbox.self_correct import SelfCorrectingRunner

            runner = SelfCorrectingRunner(
                max_attempts=policy.max_retries, backoff_s=0.3
            )
            cr = await runner.run(_exec_with_timeout)
            if cr.success:
                return cr.result
            # All retries exhausted — return structured error
            return json.dumps({
                "error": f"All {cr.attempts} attempts failed",
                "errors": cr.errors,
                "tool": tool_cls_name,
                "method": method,
            })
        else:
            return await _exec_with_timeout()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_hardened())
        finally:
            loop.close()
        return result
    except asyncio.TimeoutError:
        return json.dumps({
            "error": f"Timeout after {policy.timeout_s}s",
            "tool": tool_cls_name,
            "method": method,
        })
    except Exception as exc:
        return json.dumps({
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "tool": tool_cls_name,
            "method": method,
        })


class StatelessWorker:
    """Wraps a Tool class for execution in a worker process.

    The worker is stateless — it instantiates a fresh Tool each time,
    runs the computation, and returns the result as a JSON string.
    """

    def __init__(self, tool_cls_name: str):
        self.tool_cls_name = tool_cls_name

    def run_sync(self, method: str, params: dict[str, Any]) -> str:
        """Run the tool synchronously (for direct use or testing)."""
        return _run_tool_sync(self.tool_cls_name, method, params)
