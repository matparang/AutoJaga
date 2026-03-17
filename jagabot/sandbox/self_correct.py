"""Self-correcting runner — retry wrapper with error context accumulation."""

from __future__ import annotations

import asyncio
import logging
import traceback
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


@dataclass
class CorrectionResult:
    """Result of a self-correcting execution run."""

    success: bool
    result: Any = None
    attempts: int = 0
    errors: list[str] = field(default_factory=list)


class SelfCorrectingRunner:
    """Wrap an async callable with retry + error-context accumulation.

    On each retry the accumulated error messages from prior attempts are
    passed to an optional *on_error* callback so the caller (or an LLM)
    can adjust parameters before the next attempt.

    Usage::

        runner = SelfCorrectingRunner(max_attempts=3)
        result = await runner.run(my_async_fn, arg1, kwarg1="x")
    """

    def __init__(
        self,
        max_attempts: int = 3,
        backoff_s: float = 0.5,
        on_error: Callable[[list[str]], Awaitable[None] | None] | None = None,
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.max_attempts = max_attempts
        self.backoff_s = backoff_s
        self.on_error = on_error

    async def run(
        self,
        fn: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> CorrectionResult:
        """Execute *fn* up to *max_attempts* times, accumulating errors."""
        errors: list[str] = []

        for attempt in range(1, self.max_attempts + 1):
            try:
                result = await fn(*args, **kwargs)
                return CorrectionResult(
                    success=True, result=result, attempts=attempt, errors=errors
                )
            except Exception as exc:
                tb = traceback.format_exc()
                msg = f"Attempt {attempt}/{self.max_attempts}: {exc}"
                errors.append(msg)
                logger.warning(msg)
                logger.debug(tb)

                if self.on_error is not None:
                    try:
                        ret = self.on_error(errors)
                        if asyncio.iscoroutine(ret):
                            await ret
                    except Exception as cb_exc:
                        logger.warning(f"on_error callback failed: {cb_exc}")

                if attempt < self.max_attempts:
                    await asyncio.sleep(self.backoff_s * attempt)

        return CorrectionResult(
            success=False, result=None, attempts=self.max_attempts, errors=errors
        )

    def run_sync(
        self,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> CorrectionResult:
        """Synchronous variant — wraps *fn* in an async shell and runs it."""

        async def _wrapper() -> Any:
            return fn(*args, **kwargs)

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.run(_wrapper))
        finally:
            loop.close()
