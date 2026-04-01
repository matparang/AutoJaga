"""SubagentManager — 4-stage stateless pipeline coordinator.

Orchestrates: WebSearch → Tools → Models → Reasoning.

Each stage receives the merged output of all prior stages, runs its
tools, and returns structured JSON.  All stages are stateless — no
memory is carried between invocations.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from jagabot.subagents.stages import (
    ALL_STAGES,
    WebSearchStage,
    ToolsStage,
    ModelsStage,
    ReasoningStage,
    _BaseStage,
)

_PROMPTS_DIR = Path(__file__).parent / "prompts"

# Execution order — each stage sees merged output of all predecessors.
STAGE_ORDER = ["websearch", "tools", "models", "reasoning"]


class SubagentManager:
    """Coordinate 4 stateless subagent stages."""

    def __init__(self) -> None:
        self.prompts: dict[str, str] = self._load_prompts()

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------

    @staticmethod
    def _load_prompts() -> dict[str, str]:
        prompts: dict[str, str] = {}
        for stage_cls in ALL_STAGES.values():
            fname = stage_cls.prompt_file
            path = _PROMPTS_DIR / fname
            if path.exists():
                prompts[stage_cls.name] = path.read_text(encoding="utf-8")
            else:
                prompts[stage_cls.name] = f"(prompt file {fname} not found)"
        return prompts

    def get_prompt(self, stage_name: str) -> str | None:
        """Return the prompt markdown for *stage_name*, or ``None``."""
        return self.prompts.get(stage_name)

    # ------------------------------------------------------------------
    # Stage listing
    # ------------------------------------------------------------------

    def get_stages(self) -> list[dict[str, Any]]:
        """Return metadata for every stage in execution order."""
        return [
            {
                "name": name,
                "tools": ALL_STAGES[name].tools_used,
                "prompt_file": ALL_STAGES[name].prompt_file,
                "order": idx,
            }
            for idx, name in enumerate(STAGE_ORDER)
        ]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute_stage(
        self, stage_name: str, data: dict[str, Any],
    ) -> dict[str, Any]:
        """Run a single stage by name.

        Returns the stage output dict, or ``{"success": False, "error": ...}``
        on failure.
        """
        cls = ALL_STAGES.get(stage_name)
        if cls is None:
            return {"success": False, "error": f"Unknown stage: {stage_name}"}
        stage: _BaseStage = cls()
        try:
            result = await stage.execute(data)
            logger.debug("Stage {} completed", stage_name)
            return result
        except Exception as exc:
            logger.error("Stage {} failed: {}", stage_name, exc)
            return {"success": False, "error": str(exc), "stage": stage_name}

    async def execute_workflow(
        self,
        query: str = "",
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run the full 4-stage pipeline.

        *data* may pre-supply any keys (e.g. cached prices) — they will be
        merged into the accumulator before Stage 1 runs.

        Returns::

            {
                "web": {...},
                "tools": {...},
                "models": {...},
                "reasoning": {...},
                "success": True,
                "timestamp": "...",
            }
        """
        accumulator: dict[str, Any] = dict(data or {})
        accumulator.setdefault("query", query)

        stage_results: dict[str, Any] = {}
        start = datetime.now(timezone.utc)

        for stage_name in STAGE_ORDER:
            result = await self.execute_stage(stage_name, accumulator)
            stage_results[stage_name] = result

            if not result.get("success", False):
                logger.warning(
                    "Stage {} failed — aborting pipeline", stage_name,
                )
                stage_results["success"] = False
                stage_results["failed_stage"] = stage_name
                stage_results["timestamp"] = datetime.now(timezone.utc).isoformat()
                return stage_results

            # Merge stage output into accumulator for downstream stages.
            accumulator.update(result)

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        stage_results["success"] = True
        stage_results["elapsed_s"] = round(elapsed, 3)
        stage_results["timestamp"] = datetime.now(timezone.utc).isoformat()
        return stage_results

    # ------------------------------------------------------------------
    # Parallel analysis (v3.4 Phase 2)
    # ------------------------------------------------------------------

    async def run_parallel_analysis(
        self,
        workflow: str,
        data: dict[str, Any],
        *,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Run a predefined workflow via ParallelLab.

        Unlike ``execute_workflow`` (sequential 4-stage pipeline), this
        executes all tools in the workflow **concurrently**.

        Args:
            workflow: One of ``risk_analysis``, ``portfolio_review``, ``full_analysis``.
            data: Workflow-specific parameter dict (keys like ``mc_params``, etc.).
            timeout: Per-tool timeout in seconds.
        """
        from jagabot.lab.parallel import ParallelLab

        plab = ParallelLab()
        return await plab.execute_workflow(workflow, data, timeout=timeout)
