"""Resilient pipeline — wraps sequential subagent stages with retry and fallback."""

from __future__ import annotations

import asyncio
import logging
import traceback
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

StageFunction = Callable[..., Awaitable[dict[str, Any]]]


@dataclass
class StageResult:
    """Outcome of a single pipeline stage."""

    name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    attempts: int = 0


@dataclass
class PipelineResult:
    """Outcome of the full resilient pipeline."""

    stages: list[StageResult] = field(default_factory=list)
    degraded: bool = False

    @property
    def all_succeeded(self) -> bool:
        return all(s.success for s in self.stages)

    @property
    def final_data(self) -> dict[str, Any]:
        """Merge all stage outputs into a single dict."""
        merged: dict[str, Any] = {}
        for s in self.stages:
            merged[s.name] = s.data
        return merged


@dataclass
class StageSpec:
    """Definition of a pipeline stage."""

    name: str
    fn: StageFunction
    max_retries: int = 2
    backoff_s: float = 0.3
    fallback: dict[str, Any] | None = None


class ResilientPipeline:
    """Run a sequence of async stages with per-stage retry and partial fallback.

    If stage N fails after all retries, its ``fallback`` dict (or an empty
    dict with ``_degraded=True``) is passed downstream so stage N+1 can
    still attempt execution with degraded input.
    """

    def __init__(self, stages: list[StageSpec]):
        self.stages = stages

    async def run(self, initial_context: dict[str, Any] | None = None) -> PipelineResult:
        """Execute all stages sequentially, accumulating results."""
        context: dict[str, Any] = dict(initial_context or {})
        result = PipelineResult()

        for spec in self.stages:
            sr = await self._run_stage(spec, context)
            result.stages.append(sr)

            if sr.success:
                context[spec.name] = sr.data
            else:
                result.degraded = True
                fallback = spec.fallback or {"_degraded": True, "_error": sr.error}
                context[spec.name] = fallback
                logger.warning(
                    "Stage '%s' failed after %d attempts — using fallback",
                    spec.name,
                    sr.attempts,
                )

        return result

    async def _run_stage(
        self, spec: StageSpec, context: dict[str, Any]
    ) -> StageResult:
        """Execute a single stage with retries."""
        last_error = ""

        for attempt in range(1, spec.max_retries + 1):
            try:
                data = await spec.fn(context)
                return StageResult(
                    name=spec.name,
                    success=True,
                    data=data,
                    attempts=attempt,
                )
            except Exception as exc:
                last_error = f"Attempt {attempt}/{spec.max_retries}: {exc}"
                logger.warning("Stage '%s' %s", spec.name, last_error)
                logger.debug(traceback.format_exc())

                if attempt < spec.max_retries:
                    await asyncio.sleep(spec.backoff_s * attempt)

        return StageResult(
            name=spec.name,
            success=False,
            error=last_error,
            attempts=spec.max_retries,
        )
