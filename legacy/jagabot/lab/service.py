"""LabService — centralized tool execution with validation and logging.

Subagents and the Lab UI call LabService instead of tools directly.
This provides:
  - Parameter validation via Tool ABC's ``validate_params()``
  - Standardized result format ``{success, tool, output, execution_id, ...}``
  - Execution logging to ``~/.jagabot/lab_logs/``
  - Optional sandbox execution via SafePythonExecutor
  - Parallel execution support
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LabService:
    """Centralized tool execution service."""

    def __init__(
        self,
        log_dir: Path | str | None = None,
        sandbox_default: bool = False,
    ) -> None:
        from jagabot.ui.lab.tool_registry import LabToolRegistry

        self._registry = LabToolRegistry()
        self._sandbox_default = sandbox_default
        self._log_dir = Path(log_dir) if log_dir else Path.home() / ".jagabot" / "lab_logs"
        self._log_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        tool_name: str,
        params: dict[str, Any],
        *,
        sandbox: bool | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Execute a tool with validation and logging.

        Args:
            tool_name: Registered tool name (e.g. ``"monte_carlo"``).
            params: Parameters to pass to the tool.
            sandbox: If True, run via SafePythonExecutor. None = use default.
            timeout: Execution timeout in seconds.

        Returns:
            Standardized result dict with keys: success, tool, output,
            execution_id, execution_time, sandbox_used.
        """
        start = time.monotonic()
        exec_id = f"{tool_name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
        use_sandbox = sandbox if sandbox is not None else self._sandbox_default

        try:
            # Step 1: Look up tool
            info = self._registry.get_tool_info(tool_name)
            if not info:
                result = self._error(exec_id, tool_name, f"Unknown tool: {tool_name}", start)
                self._log_execution(exec_id, tool_name, params, result)
                return result

            tool = info["tool"]

            # Step 2: Validate parameters
            validation = self.validate_params(tool_name, params)
            if not validation["valid"]:
                result = self._error(exec_id, tool_name, validation["errors"], start)
                self._log_execution(exec_id, tool_name, params, result)
                return result

            # Step 3: Execute
            if use_sandbox:
                output = await self._execute_sandbox(tool_name, info, params, timeout)
            else:
                output = await self._execute_direct(tool, info, params, timeout)

            elapsed = time.monotonic() - start
            result = {
                "success": True,
                "tool": tool_name,
                "output": output,
                "execution_id": exec_id,
                "execution_time": round(elapsed, 3),
                "sandbox_used": use_sandbox,
            }

        except asyncio.TimeoutError:
            result = self._error(exec_id, tool_name, f"Timeout after {timeout}s", start)
        except Exception as exc:
            result = self._error(exec_id, tool_name, str(exc), start)

        # Step 4: Log
        self._log_execution(exec_id, tool_name, params, result)
        return result

    # ------------------------------------------------------------------
    # Parallel execution
    # ------------------------------------------------------------------

    async def execute_parallel(
        self,
        tasks: list[dict[str, Any]],
        *,
        sandbox: bool | None = None,
        timeout: int = 30,
    ) -> list[dict[str, Any]]:
        """Execute multiple tools concurrently.

        Each task dict must have ``tool`` (str) and ``params`` (dict).
        """
        coros = [
            self.execute(t["tool"], t["params"], sandbox=sandbox, timeout=timeout)
            for t in tasks
        ]
        return list(await asyncio.gather(*coros, return_exceptions=False))

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_params(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Validate parameters against tool schema.

        Returns ``{"valid": True}`` or ``{"valid": False, "errors": [...]}``.
        """
        info = self._registry.get_tool_info(tool_name)
        if not info:
            return {"valid": False, "errors": [f"Unknown tool: {tool_name}"]}

        tool = info["tool"]
        methods = info.get("methods", [])

        # For dispatch tools, validate method + inner params
        if methods:
            method = params.get("method")
            if method and method not in methods:
                return {
                    "valid": False,
                    "errors": [f"Unknown method '{method}' for {tool_name}. Available: {methods}"],
                }

        # Delegate to Tool ABC's validate_params
        try:
            errors = tool.validate_params(params)
        except Exception as exc:
            errors = [f"Validation error: {exc}"]

        return {"valid": len(errors) == 0, "errors": errors} if errors else {"valid": True}

    # ------------------------------------------------------------------
    # Tool listing (convenience)
    # ------------------------------------------------------------------

    def list_tools(self) -> list[str]:
        """Return all available tool names."""
        return sorted(self._registry.get_tools().keys())

    def tool_count(self) -> int:
        """Number of registered tools."""
        return self._registry.tool_count()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _execute_direct(
        self, tool: Any, info: dict, params: dict, timeout: int,
    ) -> Any:
        """Execute tool directly via its async execute() method."""
        methods = info.get("methods", [])
        method = params.get("method")

        if methods and method:
            # Dispatch tool: tool.execute(method=..., params=...)
            inner = params.get("params", {})
            raw = await asyncio.wait_for(
                tool.execute(method=method, params=inner),
                timeout=timeout,
            )
        else:
            # Simple tool or dispatch without method
            clean = {k: v for k, v in params.items() if k not in ("method", "params")}
            raw = await asyncio.wait_for(
                tool.execute(**clean),
                timeout=timeout,
            )

        return self._parse_output(raw)

    async def _execute_sandbox(
        self, tool_name: str, info: dict, params: dict, timeout: int,
    ) -> Any:
        """Execute via SafePythonExecutor (Docker / subprocess)."""
        from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig
        from jagabot.ui.lab.code_generator import CodeGenerator

        codegen = CodeGenerator()
        method = params.get("method")
        code = codegen.generate(tool_name, params, method=method)

        config = SandboxConfig(timeout_s=timeout)
        executor = SafePythonExecutor(config=config)
        result = await executor.execute(code, subagent="lab_service", calc_type=tool_name)

        if result.success:
            return self._parse_output(result.output)
        raise RuntimeError(f"Sandbox execution failed: {result.error}")

    @staticmethod
    def _parse_output(raw: Any) -> Any:
        """Try to parse JSON string into dict, otherwise return as-is."""
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                return {"raw": raw}
        return raw

    def _log_execution(
        self, exec_id: str, tool: str, params: dict, result: dict,
    ) -> None:
        """Write execution log to JSON file."""
        try:
            log_entry = {
                "execution_id": exec_id,
                "tool": tool,
                "params": params,
                "success": result.get("success", False),
                "execution_time": result.get("execution_time"),
                "sandbox_used": result.get("sandbox_used", False),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            log_file = self._log_dir / f"{exec_id}.json"
            log_file.write_text(json.dumps(log_entry, indent=2, default=str), encoding="utf-8")
        except Exception as exc:
            logger.debug("Failed to write execution log: %s", exc)

    @staticmethod
    def _error(exec_id: str, tool: str, error: Any, start: float) -> dict[str, Any]:
        return {
            "success": False,
            "tool": tool,
            "error": error,
            "execution_id": exec_id,
            "execution_time": round(time.monotonic() - start, 3),
            "sandbox_used": False,
        }
