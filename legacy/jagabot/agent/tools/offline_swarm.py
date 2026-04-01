"""LLM-callable tool for running Level-4 offline swarm tests."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from jagabot.agent.tools.base import Tool


class OfflineSwarmTool(Tool):
    """Runs a Level-4 offline swarm test with pluggable attacks."""

    @property
    def name(self) -> str:
        return "run_swarm"

    @property
    def description(self) -> str:
        return (
            "Run a Level-4 offline swarm test. Generates data pools, applies "
            "adversarial attacks (negative spoof, NaN injection, zero-divide, "
            "duplicate block), repairs all corruption, verifies integrity, "
            "computes stats, and writes an audit manifest + report. "
            "Returns a text summary of the results."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pools": {
                    "type": "integer",
                    "description": "Total number of data pools (default 12)",
                    "default": 12,
                },
                "seed": {
                    "type": "integer",
                    "description": "Reproducibility seed (omit for random)",
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Simulate without writing files",
                    "default": False,
                },
                "attack_summary": {
                    "type": "boolean",
                    "description": "Include detailed attack log in output",
                    "default": False,
                },
            },
            "required": [],
        }

    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace

    async def execute(self, **kwargs: Any) -> str:
        from jagabot.swarm.offline_swarm import run_offline_swarm

        pools = kwargs.get("pools", 12)
        seed = kwargs.get("seed")
        dry_run = kwargs.get("dry_run", False)
        show_attacks = kwargs.get("attack_summary", False)

        agents_count = 4
        ppa = max(1, pools // agents_count)

        status_lines: list[str] = []
        cb = status_lines.append if show_attacks else None

        result = run_offline_swarm(
            workspace=self._workspace,
            seed=seed,
            pools_per_agent=ppa,
            dry_run=dry_run,
            attack_summary_callback=cb,
        )

        output = result.summary()
        if status_lines:
            output = "\n".join(status_lines) + "\n\n" + output

        return output
