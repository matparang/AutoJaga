"""Manage the local DeepSeek MCP server process."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

_REPO_PATH = Path(__file__).parent.parent.parent / "deepseek-mcp-server"
_DEFAULT_PORT = 3001
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PATH = "/mcp"


class MCPServerManager:
    """Start, stop, and query the local DeepSeek MCP server (HTTP transport)."""

    def __init__(
        self,
        repo_path: Path | None = None,
        port: int = _DEFAULT_PORT,
        host: str = _DEFAULT_HOST,
        mcp_path: str = _DEFAULT_PATH,
    ) -> None:
        self.repo_path = repo_path or _REPO_PATH
        self.port = port
        self.host = host
        self.mcp_path = mcp_path
        self._process: subprocess.Popen | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def entry_point(self) -> Path:
        return self.repo_path / "build" / "index.js"

    @property
    def is_built(self) -> bool:
        return self.entry_point.exists()

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    # ------------------------------------------------------------------
    # Process management
    # ------------------------------------------------------------------

    def start(self, deepseek_api_key: str = "") -> dict[str, Any]:
        """Start the MCP server in Streamable HTTP mode."""
        if not self.is_built:
            return {"success": False, "error": f"Server not built: {self.entry_point}"}

        if self._process and self._process.poll() is None:
            return {"success": True, "pid": self._process.pid, "already_running": True}

        env_vars = {
            "MCP_TRANSPORT": "streamable-http",
            "MCP_HTTP_HOST": self.host,
            "MCP_HTTP_PORT": str(self.port),
            "MCP_HTTP_PATH": self.mcp_path,
            "MCP_HTTP_STATEFUL_SESSION": "false",
        }
        if deepseek_api_key:
            env_vars["DEEPSEEK_API_KEY"] = deepseek_api_key

        import os
        merged_env = {**os.environ, **env_vars}

        self._process = subprocess.Popen(
            ["node", str(self.entry_point)],
            cwd=str(self.repo_path),
            env=merged_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Brief wait for server to bind
        time.sleep(0.5)
        if self._process.poll() is not None:
            stderr = self._process.stderr.read().decode(errors="replace") if self._process.stderr else ""
            return {"success": False, "error": f"Process exited early: {stderr[:200]}"}

        return {"success": True, "pid": self._process.pid}

    def stop(self) -> dict[str, Any]:
        """Terminate the MCP server process."""
        if self._process is None:
            return {"success": False, "error": "No managed process"}
        if self._process.poll() is not None:
            self._process = None
            return {"success": False, "error": "Process already exited"}
        self._process.terminate()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
        self._process = None
        return {"success": True}

    def status(self) -> dict[str, Any]:
        """Return the server status dict."""
        if self._process is None:
            return {"status": "stopped", "pid": None}
        rc = self._process.poll()
        if rc is not None:
            return {"status": "stopped", "pid": self._process.pid, "exit_code": rc}
        return {
            "status": "running",
            "pid": self._process.pid,
            "url": self.base_url,
            "path": self.mcp_path,
        }

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def detect_info(self) -> dict[str, Any]:
        """Return static info about the local repo."""
        return {
            "repo_path": str(self.repo_path),
            "is_built": self.is_built,
            "entry_point": str(self.entry_point),
            "language": "node",
            "transport": "streamable-http",
            "port": self.port,
            "host": self.host,
            "mcp_path": self.mcp_path,
        }
