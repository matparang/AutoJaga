"""BaseSubagent — base class with LabService integration.

Subagents that extend BaseSubagent get ``self.lab`` (a LabService instance)
and can call ``await self.execute_tool(name, params)`` for centralized
execution with validation, logging, and optional sandboxing.
"""

from __future__ import annotations

from typing import Any

from jagabot.lab.service import LabService


class BaseSubagent:
    """Base class for subagents with centralized LabService access."""

    def __init__(self, lab: LabService | None = None) -> None:
        self.lab = lab or LabService()

    async def execute_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
        *,
        sandbox: bool = False,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Execute a tool via LabService.

        Returns standardized result dict with ``success``, ``output``, etc.
        """
        return await self.lab.execute(
            tool_name, params, sandbox=sandbox, timeout=timeout,
        )

    async def execute_tools_parallel(
        self,
        tasks: list[dict[str, Any]],
        *,
        sandbox: bool = False,
        timeout: int = 30,
    ) -> list[dict[str, Any]]:
        """Execute multiple tools concurrently via LabService."""
        return await self.lab.execute_parallel(
            tasks, sandbox=sandbox, timeout=timeout,
        )
