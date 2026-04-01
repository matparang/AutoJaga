"""Utility functions for AutoJaga."""

from pathlib import Path
from datetime import datetime


def ensure_dir(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_path() -> Path:
    """Get the autojaga data directory (~/.autojaga)."""
    return ensure_dir(Path.home() / ".autojaga")


def get_workspace_path(workspace: str | None = None) -> Path:
    """Get the workspace path."""
    if workspace:
        path = Path(workspace).expanduser()
    else:
        path = Path.home() / ".autojaga" / "workspace"
    return ensure_dir(path)


def timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


def truncate_string(s: str, max_len: int = 100, suffix: str = "...") -> str:
    """Truncate a string to max length, adding suffix if truncated."""
    if len(s) <= max_len:
        return s
    return s[: max_len - len(suffix)] + suffix
