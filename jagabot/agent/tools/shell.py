"""Shell execution tool."""

import asyncio
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jagabot.agent.tools.base import Tool

if TYPE_CHECKING:
    from jagabot.core.resource_guard import ResourceGuard


class ExecTool(Tool):
    """Tool to execute shell commands."""
    
    # Paths always allowed even under restrict_to_workspace
    DEFAULT_SAFE_PATHS = [
        "/tmp",
        "/usr/bin", "/usr/local/bin", "/bin", "/usr/sbin",
        "/root/.jagabot",
        "/root/nanojaga",
    ]
    
    def __init__(
        self,
        timeout: int = 60,
        working_dir: str | None = None,
        deny_patterns: list[str] | None = None,
        allow_patterns: list[str] | None = None,
        restrict_to_workspace: bool = False,
        extra_safe_paths: list[str] | None = None,
        resource_guard: "ResourceGuard | None" = None,
    ):
        self.timeout = timeout
        self.working_dir = working_dir
        self.deny_patterns = deny_patterns or [
            r"\brm\s+-[rf]{1,2}\b",          # rm -r, rm -rf, rm -fr
            r"\bdel\s+/[fq]\b",              # del /f, del /q
            r"\brmdir\s+/s\b",               # rmdir /s
            r"\b(format|mkfs|diskpart)\b",   # disk operations
            r"\bdd\s+if=",                   # dd
            r">\s*/dev/sd",                  # write to disk
            r"\b(shutdown|reboot|poweroff)\b",  # system power
            r":\(\)\s*\{.*\};\s*:",          # fork bomb
        ]
        self.allow_patterns = allow_patterns or []
        self.restrict_to_workspace = restrict_to_workspace
        self.safe_paths = [Path(p).resolve() for p in self.DEFAULT_SAFE_PATHS + (extra_safe_paths or [])]
        self._resource_guard = resource_guard
    
    @property
    def name(self) -> str:
        return "exec"
    
    @property
    def description(self) -> str:
        return "Execute a shell command and return its output. Use with caution."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory for the command"
                }
            },
            "required": ["command"]
        }
    
    async def execute(self, command: str, working_dir: str | None = None, **kwargs: Any) -> str:
        cwd = working_dir or self.working_dir or os.getcwd()
        guard_error = self._guard_command(command, cwd)
        if guard_error:
            return guard_error

        try:
            preexec = self._resource_guard.preexec_fn if self._resource_guard else None
            # Use bash explicitly for proper brace expansion and shell features
            process = await asyncio.create_subprocess_exec(
                "bash", "-c", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                preexec_fn=preexec,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return f"Error: Command timed out after {self.timeout} seconds"
            
            output_parts = []
            
            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))
            
            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"STDERR:\n{stderr_text}")
            
            if process.returncode != 0:
                output_parts.append(f"\nExit code: {process.returncode}")
            
            result = "\n".join(output_parts) if output_parts else "(no output)"

            # Truncate very long output (increased for full file listings)
            max_len = 50000
            if len(result) > max_len:
                result = result[:max_len] + f"\n... (truncated, {len(result) - max_len} more chars)"

            return result
            
        except Exception as e:
            return f"Error executing command: {str(e)}"

    def _guard_command(self, command: str, cwd: str) -> str | None:
        """Best-effort safety guard for potentially destructive commands."""
        cmd = command.strip()
        lower = cmd.lower()

        for pattern in self.deny_patterns:
            if re.search(pattern, lower):
                return "Error: Command blocked by safety guard (dangerous pattern detected)"

        if self.allow_patterns:
            if not any(re.search(p, lower) for p in self.allow_patterns):
                return "Error: Command blocked by safety guard (not in allowlist)"

        if self.restrict_to_workspace:
            if "..\\" in cmd or "../" in cmd:
                return "Error: Command blocked by safety guard (path traversal detected)"

            cwd_path = Path(cwd).resolve()
            allowed_roots = [cwd_path] + self.safe_paths
            
            # Convert all allowed roots to strings for prefix matching
            allowed_prefixes = [str(r) for r in allowed_roots]

            # Extract all absolute paths from the command
            # Match paths starting with / followed by valid path characters
            posix_paths = re.findall(r'/(?:[\w.\-]+/)*[\w.\-]*', cmd)
            
            for raw_path in posix_paths:
                if not raw_path or raw_path == '/':
                    continue
                try:
                    p = Path(raw_path).resolve()
                    p_str = str(p)
                    # Check if path starts with any allowed prefix
                    if not any(p_str.startswith(prefix) for prefix in allowed_prefixes):
                        return f"Error: Command blocked by safety guard (path outside allowed dirs): {raw_path}"
                except Exception:
                    continue

        return None
