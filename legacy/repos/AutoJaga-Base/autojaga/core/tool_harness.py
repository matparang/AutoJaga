"""
Tool Harness — Anti-fabrication and execution tracking.

Tracks every tool invocation and runs fabrication detection
to catch hallucinated tool results.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any


# Fabrication detection patterns
_PAST_CLAIM = re.compile(
    r"(?:created|wrote|written|saved|generated|made|produced)\s",
    re.IGNORECASE,
)

_FILENAME_PATTERN = re.compile(
    r"[`\"']([^`\"']*?\.(?:txt|py|json|md|yaml|yml|csv|log))[`\"']",
    re.IGNORECASE,
)


class ToolHarness:
    """
    Universal tool execution harness.
    
    Tracks tool invocations, timing, and runs anti-fabrication checks.
    """
    
    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self._executions: dict[str, dict[str, Any]] = {}
        self._completed_files: set[str] = set()
    
    def start(self, tool_id: str, tool_name: str) -> None:
        """Record tool execution start."""
        self._executions[tool_id] = {
            "name": tool_name,
            "start_time": time.monotonic(),
            "status": "running",
        }
    
    def complete(
        self,
        tool_id: str,
        result: str,
        result_file: str | None = None,
    ) -> None:
        """Record tool execution completion."""
        if tool_id not in self._executions:
            return
        
        exec_record = self._executions[tool_id]
        exec_record["end_time"] = time.monotonic()
        exec_record["elapsed"] = exec_record["end_time"] - exec_record["start_time"]
        exec_record["status"] = "completed"
        exec_record["result_preview"] = result[:200] if result else ""
        
        if result_file:
            self._completed_files.add(result_file)
    
    def fail(self, tool_id: str, error: str) -> None:
        """Record tool execution failure."""
        if tool_id not in self._executions:
            return
        
        exec_record = self._executions[tool_id]
        exec_record["end_time"] = time.monotonic()
        exec_record["elapsed"] = exec_record["end_time"] - exec_record["start_time"]
        exec_record["status"] = "failed"
        exec_record["error"] = error
    
    def check_fabrication(self, response: str) -> list[str]:
        """
        Check response for fabricated claims.
        
        Returns list of warnings if fabrication detected.
        """
        warnings = []
        
        # Check for file creation claims
        if _PAST_CLAIM.search(response):
            # Extract claimed filenames
            matches = _FILENAME_PATTERN.findall(response)
            
            for filename in matches:
                # Check if file was actually created
                if filename not in self._completed_files:
                    # Check if file exists on disk
                    p = self.workspace / filename
                    if not p.exists():
                        warnings.append(
                            f"⚠️ Fabrication detected: claims to have created '{filename}' "
                            f"but no write_file tool was called and file doesn't exist."
                        )
        
        return warnings
    
    def get_execution_summary(self) -> dict[str, Any]:
        """Get summary of tool executions."""
        completed = [e for e in self._executions.values() if e["status"] == "completed"]
        failed = [e for e in self._executions.values() if e["status"] == "failed"]
        
        return {
            "total": len(self._executions),
            "completed": len(completed),
            "failed": len(failed),
            "tools_used": list(set(e["name"] for e in self._executions.values())),
            "total_time": sum(e.get("elapsed", 0) for e in self._executions.values()),
        }
    
    def reset(self) -> None:
        """Reset harness for new turn."""
        self._executions = {}
        self._completed_files = set()
