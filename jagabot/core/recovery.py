"""
Workspace Recovery — checkpoint/restore for the agent workspace.

Creates lightweight snapshots of critical workspace files before risky
operations. If a catastrophic failure is detected, the workspace can
be restored from the most recent checkpoint.

Checkpoints are stored in ``~/.jagabot/checkpoints/{id}/`` with a
retention policy of the last N snapshots.
"""

from __future__ import annotations

import json
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

from loguru import logger

_MAX_CHECKPOINTS = 3
_MAX_FILE_SIZE = 1024 * 1024  # 1 MB — skip large files
_SKIP_DIRS = frozenset({
    "__pycache__", ".git", "node_modules", "venv",
    "tri_agent_sandbox", "quad_agent_sandbox",
    "checkpoints", "transcripts",
})


class WorkspaceCheckpoint:
    """
    Manages workspace snapshots for self-healing recovery.

    Usage:
        cp = WorkspaceCheckpoint(workspace, checkpoint_dir)

        # Manual snapshot/restore
        cid = cp.snapshot()
        cp.restore(cid)

        # Context manager for risky operations
        with cp.guarded():
            ... risky operation ...
        # Auto-restores on exception
    """

    def __init__(
        self,
        workspace: Path,
        checkpoint_dir: Path | None = None,
        max_checkpoints: int = _MAX_CHECKPOINTS,
    ) -> None:
        self.workspace = Path(workspace)
        self.checkpoint_dir = checkpoint_dir or (
            Path.home() / ".jagabot" / "checkpoints"
        )
        self.max_checkpoints = max_checkpoints
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def snapshot(self, label: str = "") -> str:
        """
        Create a snapshot of workspace files.

        Returns:
            checkpoint_id string (timestamp-based)
        """
        cid = f"{int(time.time())}_{label}" if label else str(int(time.time()))
        dest = self.checkpoint_dir / cid
        dest.mkdir(parents=True, exist_ok=True)

        file_count = 0
        for item in self.workspace.rglob("*"):
            if not item.is_file():
                continue
            # Skip excluded directories
            if any(skip in item.parts for skip in _SKIP_DIRS):
                continue
            # Skip large files
            try:
                if item.stat().st_size > _MAX_FILE_SIZE:
                    continue
            except OSError:
                continue

            rel = item.relative_to(self.workspace)
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(item, target)
                file_count += 1
            except (OSError, PermissionError) as e:
                logger.debug(f"Checkpoint skip {rel}: {e}")

        # Write manifest
        manifest = {
            "checkpoint_id": cid,
            "timestamp": time.time(),
            "workspace": str(self.workspace),
            "file_count": file_count,
            "label": label,
        }
        (dest / "_manifest.json").write_text(json.dumps(manifest, indent=2))

        logger.info(f"Checkpoint created: {cid} ({file_count} files)")
        self._prune()
        return cid

    def restore(self, checkpoint_id: str) -> bool:
        """
        Restore workspace from a checkpoint.

        Returns True if successful, False if checkpoint not found.
        """
        src = self.checkpoint_dir / checkpoint_id
        if not src.exists():
            logger.error(f"Checkpoint not found: {checkpoint_id}")
            return False

        file_count = 0
        for item in src.rglob("*"):
            if not item.is_file() or item.name == "_manifest.json":
                continue
            rel = item.relative_to(src)
            target = self.workspace / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(item, target)
                file_count += 1
            except (OSError, PermissionError) as e:
                logger.warning(f"Restore failed for {rel}: {e}")

        logger.info(f"Restored checkpoint {checkpoint_id} ({file_count} files)")
        return True

    def list_checkpoints(self) -> list[dict]:
        """List available checkpoints (newest first)."""
        results = []
        for d in sorted(self.checkpoint_dir.iterdir(), reverse=True):
            if not d.is_dir():
                continue
            manifest_path = d / "_manifest.json"
            if manifest_path.exists():
                try:
                    results.append(json.loads(manifest_path.read_text()))
                except (json.JSONDecodeError, OSError):
                    results.append({"checkpoint_id": d.name})
        return results

    @contextmanager
    def guarded(self, label: str = "auto"):
        """
        Context manager that snapshots before and restores on failure.

        Usage:
            with checkpoint.guarded("before_tool_run"):
                ... risky code ...
        """
        cid = self.snapshot(label)
        try:
            yield cid
        except Exception:
            logger.warning(f"Guarded operation failed — restoring checkpoint {cid}")
            self.restore(cid)
            raise

    def _prune(self) -> None:
        """Remove old checkpoints beyond retention limit."""
        dirs = sorted(
            [d for d in self.checkpoint_dir.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        for old_dir in dirs[self.max_checkpoints:]:
            try:
                shutil.rmtree(old_dir)
                logger.debug(f"Pruned old checkpoint: {old_dir.name}")
            except OSError as e:
                logger.debug(f"Prune failed for {old_dir.name}: {e}")
