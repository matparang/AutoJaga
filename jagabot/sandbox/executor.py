"""Safe Python executor — runs code in Docker containers or subprocess fallback.

v2.3: Added SandboxTracker integration and config-from-Pydantic support.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from jagabot.sandbox.tracker import SandboxTracker

logger = logging.getLogger(__name__)

_DOCKER_IMAGE = "python:3.12-slim"


@dataclass
class ExecutionResult:
    """Result of a sandboxed code execution."""

    success: bool
    output: str = ""
    error: str = ""
    exit_code: int = 0
    engine: str = "none"  # "docker" | "subprocess" | "none"
    duration_ms: float = 0.0


@dataclass
class SandboxConfig:
    """Security policy for sandboxed execution."""

    timeout_s: int = 10
    memory_limit: str = "128m"
    cpu_limit: float = 0.5
    network: bool = False
    image: str = _DOCKER_IMAGE
    max_output: int = 10_000
    allow_subprocess_fallback: bool = True
    force_fallback: bool = False  # skip Docker even if available

    @classmethod
    def from_pydantic(cls, cfg: Any) -> SandboxConfig:
        """Build from a ``SandboxToolConfig`` Pydantic model."""
        return cls(
            timeout_s=getattr(cfg, "timeout", 10),
            memory_limit=getattr(cfg, "memory_limit", "128m"),
            cpu_limit=getattr(cfg, "cpu_limit", 0.5),
            network=getattr(cfg, "network", False),
            image=getattr(cfg, "image", _DOCKER_IMAGE),
            allow_subprocess_fallback=getattr(cfg, "allow_fallback", True),
            force_fallback=getattr(cfg, "force_fallback", False),
        )


class SafePythonExecutor:
    """Execute arbitrary Python code in an isolated environment.

    Tries Docker first (no network, memory/CPU capped). If Docker is
    unavailable and ``allow_subprocess_fallback`` is True, runs in a
    restricted subprocess instead.

    v2.3: accepts an optional ``SandboxTracker`` for execution logging.
    """

    def __init__(
        self,
        config: SandboxConfig | None = None,
        tracker: SandboxTracker | None = None,
    ):
        self.config = config or SandboxConfig()
        self.tracker = tracker
        self._docker: str | None = shutil.which("docker")

    @property
    def docker_available(self) -> bool:
        return self._docker is not None and not self.config.force_fallback

    async def execute(
        self,
        code: str,
        *,
        subagent: str = "",
        calc_type: str = "",
    ) -> ExecutionResult:
        """Run *code* in the safest available sandbox."""
        t0 = time.monotonic()

        if self.docker_available:
            result = await self._run_docker(code)
        elif self.config.allow_subprocess_fallback:
            result = await self._run_subprocess(code)
        else:
            result = ExecutionResult(
                success=False,
                error="Docker not available and subprocess fallback disabled",
            )

        result.duration_ms = (time.monotonic() - t0) * 1000

        # Log to tracker if present
        if self.tracker is not None:
            try:
                self.tracker.log_execution(
                    code=code,
                    success=result.success,
                    exec_time_ms=result.duration_ms,
                    engine=result.engine,
                    subagent=subagent,
                    calc_type=calc_type,
                    error=result.error,
                )
            except Exception as exc:
                logger.debug("Tracker log failed: %s", exc)

        return result

    # ------------------------------------------------------------------
    # Docker execution
    # ------------------------------------------------------------------

    async def _run_docker(self, code: str) -> ExecutionResult:
        """Execute code inside an ephemeral Docker container."""
        tmp = None
        try:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".py", mode="w", delete=False, prefix="jaga_sandbox_"
            )
            tmp.write(code)
            tmp.flush()
            tmp_path = Path(tmp.name)
            tmp.close()

            cmd = [
                self._docker or "docker",
                "run",
                "--rm",
                f"--memory={self.config.memory_limit}",
                f"--cpus={self.config.cpu_limit}",
                "--pids-limit=64",
                "--read-only",
                "--tmpfs=/tmp:size=32m",
            ]

            if not self.config.network:
                cmd.append("--network=none")

            cmd += [
                "-v",
                f"{tmp_path}:/sandbox/script.py:ro",
                self.config.image,
                "python",
                "/sandbox/script.py",
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.config.timeout_s,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ExecutionResult(
                    success=False,
                    error=f"Timeout after {self.config.timeout_s}s",
                    exit_code=-1,
                    engine="docker",
                )

            out = self._truncate(stdout.decode("utf-8", errors="replace"))
            err = stderr.decode("utf-8", errors="replace")

            return ExecutionResult(
                success=proc.returncode == 0,
                output=out,
                error=err if proc.returncode != 0 else "",
                exit_code=proc.returncode or 0,
                engine="docker",
            )

        except FileNotFoundError:
            logger.warning("Docker binary not found at runtime, falling back")
            if self.config.allow_subprocess_fallback:
                return await self._run_subprocess(code)
            return ExecutionResult(
                success=False, error="Docker binary vanished", engine="docker"
            )
        except Exception as exc:
            return ExecutionResult(
                success=False, error=f"Docker error: {exc}", engine="docker"
            )
        finally:
            if tmp is not None:
                try:
                    Path(tmp.name).unlink(missing_ok=True)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Subprocess fallback
    # ------------------------------------------------------------------

    async def _run_subprocess(self, code: str) -> ExecutionResult:
        """Fallback: run code via ``python -c`` in a subprocess (no Docker)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3",
                "-c",
                code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.config.timeout_s,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ExecutionResult(
                    success=False,
                    error=f"Timeout after {self.config.timeout_s}s",
                    exit_code=-1,
                    engine="subprocess",
                )

            out = self._truncate(stdout.decode("utf-8", errors="replace"))
            err = stderr.decode("utf-8", errors="replace")

            return ExecutionResult(
                success=proc.returncode == 0,
                output=out,
                error=err if proc.returncode != 0 else "",
                exit_code=proc.returncode or 0,
                engine="subprocess",
            )
        except Exception as exc:
            return ExecutionResult(
                success=False, error=f"Subprocess error: {exc}", engine="subprocess"
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _truncate(self, text: str) -> str:
        mx = self.config.max_output
        if len(text) > mx:
            return text[:mx] + f"\n... (truncated, {len(text) - mx} more chars)"
        return text
