"""Notebook manager — save/load analysis cells as JSON files.

Notebooks live in ``~/.jagabot/notebooks/{name}.json`` so they persist
across sessions without polluting the project tree.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path.home() / ".jagabot" / "notebooks"


class NotebookManager:
    """Manage Lab analysis notebooks (JSON-based)."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else _DEFAULT_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        safe = name.replace("/", "_").replace("\\", "_")
        if not safe.endswith(".json"):
            safe += ".json"
        return self.base_dir / safe

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_cell(
        self,
        notebook_name: str,
        tool_name: str,
        params: dict[str, Any],
        code: str,
        result: str,
    ) -> None:
        """Append a cell to a notebook."""
        path = self._path(notebook_name)
        cells = self._read(path)
        cells.append({
            "tool": tool_name,
            "params": params,
            "code": code,
            "result": result,
            "timestamp": time.time(),
        })
        self._write(path, cells)
        logger.debug("Saved cell to %s (%d cells)", path, len(cells))

    def load_notebook(self, name: str) -> list[dict[str, Any]]:
        """Load all cells from a notebook. Returns [] if not found."""
        return self._read(self._path(name))

    def list_notebooks(self) -> list[str]:
        """Return names of all saved notebooks."""
        return sorted(
            p.stem for p in self.base_dir.glob("*.json") if p.is_file()
        )

    def new_notebook(self, name: str) -> None:
        """Create an empty notebook (overwrites if exists)."""
        self._write(self._path(name), [])

    def delete_notebook(self, name: str) -> bool:
        """Delete a notebook. Returns True if deleted."""
        path = self._path(name)
        if path.exists():
            path.unlink()
            return True
        return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _read(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    @staticmethod
    def _write(path: Path, cells: list[dict[str, Any]]) -> None:
        path.write_text(
            json.dumps(cells, indent=2, default=str),
            encoding="utf-8",
        )
