#!/usr/bin/env python3
"""
workspace_enforcer.py — Enforce that all agent file operations stay within workspace.
Created: 2026-03-11 via jagafilefix.md remediation.

Usage:
    from jagabot.tools.workspace_enforcer import WorkspaceEnforcer, safe_path

    # Get a safe workspace-relative path
    path = WorkspaceEnforcer.get_path("my_file.py")

    # Validate a path is within workspace (raises if not)
    WorkspaceEnforcer.assert_within_workspace("/root/.jagabot/workspace/my_file.py")

    # Use as decorator to auto-redirect first str arg to workspace
    @WorkspaceEnforcer.verify_path
    def write_something(filepath, content):
        with open(filepath, "w") as f:
            f.write(content)
"""

import os
import functools
from pathlib import Path

WORKSPACE = Path.home() / ".jagabot" / "workspace"
TOOLS_DIR = Path("/root/nanojaga/jagabot/tools")
LOGS_DIR = Path.home() / ".jagabot" / "logs"
PROOFS_DIR = Path.home() / ".jagabot" / "proofs"

# All dirs the agent is explicitly allowed to write to
ALLOWED_DIRS = (
    WORKSPACE,
    LOGS_DIR,
    PROOFS_DIR,
)


class WorkspaceEnforcer:
    """
    Utility class to ensure file operations stay within approved directories.
    Never raises silently — either returns a safe path or raises ValueError.
    """

    @classmethod
    def get_path(cls, filename: str, subdir: str | None = None) -> Path:
        """
        Return an absolute path inside the workspace for a given filename.
        Strips any leading directory components — basename only is placed in workspace.

        Args:
            filename: File name (basename extracted if a full path is given).
            subdir:   Optional subdirectory within workspace (e.g. "memory", "tools").
        """
        basename = Path(filename).name
        base = WORKSPACE / subdir if subdir else WORKSPACE
        base.mkdir(parents=True, exist_ok=True)
        return base / basename

    @classmethod
    def is_within_workspace(cls, path: str | Path) -> bool:
        """Return True if path is inside one of the allowed directories."""
        resolved = Path(path).expanduser().resolve()
        return any(
            str(resolved).startswith(str(allowed_dir.expanduser().resolve()))
            for allowed_dir in ALLOWED_DIRS
        )

    @classmethod
    def assert_within_workspace(cls, path: str | Path) -> Path:
        """
        Return resolved Path if allowed; raise ValueError otherwise.
        Use this as a guard at the top of any tool's execute() method.
        """
        resolved = Path(path).expanduser().resolve()
        if not cls.is_within_workspace(resolved):
            raise ValueError(
                f"Path '{resolved}' is outside the allowed workspace. "
                f"Use a path within: {', '.join(str(d) for d in ALLOWED_DIRS)}"
            )
        return resolved

    @classmethod
    def redirect_to_workspace(cls, path: str | Path, subdir: str | None = None) -> Path:
        """
        If path is outside workspace, redirect it to workspace/basename.
        Logs a warning. Use this for lenient enforcement.
        """
        if cls.is_within_workspace(path):
            return Path(path).expanduser().resolve()
        safe = cls.get_path(str(path), subdir=subdir)
        from loguru import logger
        logger.warning(
            f"WorkspaceEnforcer: redirected '{path}' → '{safe}' (outside workspace)"
        )
        return safe

    @classmethod
    def verify_path(cls, func):
        """
        Decorator. Inspects the first positional str argument that looks like a file
        path and redirects it to workspace if it falls outside allowed dirs.
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            args = list(args)
            for i, arg in enumerate(args):
                if isinstance(arg, (str, Path)) and (
                    "/" in str(arg) or str(arg).endswith((".py", ".md", ".json", ".jsonl", ".log", ".txt"))
                ):
                    args[i] = cls.redirect_to_workspace(arg)
                    break
            return func(*args, **kwargs)
        return wrapper


def safe_path(filename: str, subdir: str | None = None) -> Path:
    """Shortcut: return a workspace-safe path for filename."""
    return WorkspaceEnforcer.get_path(filename, subdir=subdir)


def workspace_summary() -> dict:
    """Return current workspace usage summary for reporting."""
    summary: dict = {
        "workspace": str(WORKSPACE),
        "allowed_dirs": [str(d) for d in ALLOWED_DIRS],
        "workspace_exists": WORKSPACE.exists(),
        "subdirs": [],
    }
    if WORKSPACE.exists():
        summary["subdirs"] = [
            d.name for d in WORKSPACE.iterdir() if d.is_dir()
        ]
    return summary


if __name__ == "__main__":
    import json
    print(json.dumps(workspace_summary(), indent=2))
    # Test redirect
    safe = WorkspaceEnforcer.redirect_to_workspace("/root/nanojaga/tools/test.py")
    print(f"Redirected path: {safe}")
    print(f"Is within workspace: {WorkspaceEnforcer.is_within_workspace(safe)}")
