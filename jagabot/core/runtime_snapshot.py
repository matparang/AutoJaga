"""
RuntimeSnapshotBuilder

Saves recoverable state snapshots during task execution.
Allows recovery from crashes, timeouts, or context loss.

Snapshots capture:
  - Current task and phase
  - Tools already executed and results
  - Partial response so far
  - Session key and turn ID
  - Timestamp

Recovery:
  - On crash/timeout → load latest snapshot
  - Resume from last successful tool call
  - Inject snapshot context into new session
"""

from __future__ import annotations
import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from loguru import logger


@dataclass
class RuntimeSnapshot:
    """A point-in-time snapshot of agent execution state."""
    snapshot_id:   str
    session_key:   str
    turn_id:       str
    timestamp:     str
    task:          str          # original user query
    phase:         str          # current execution phase
    tools_executed: list[dict]  # [{tool, args, result_summary}]
    partial_response: str       # response built so far
    tool_count:    int
    is_complete:   bool = False


class RuntimeSnapshotBuilder:
    """
    Builds and manages runtime state snapshots.
    Enables crash recovery and task resumption.
    """

    MAX_SNAPSHOTS = 10  # keep last N snapshots
    SNAPSHOT_INTERVAL = 3  # save every N tool calls

    def __init__(self, workspace: Path):
        self.workspace    = Path(workspace)
        self.snapshot_dir = self.workspace / "snapshots"
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._current: RuntimeSnapshot | None = None
        self._tool_count = 0

    def start_turn(self, task: str, session_key: str, turn_id: str) -> RuntimeSnapshot:
        """Start a new snapshot for a turn."""
        snap = RuntimeSnapshot(
            snapshot_id    = f"{session_key}_{int(time.time())}",
            session_key    = session_key,
            turn_id        = turn_id,
            timestamp      = datetime.now().isoformat(),
            task           = task[:200],
            phase          = "init",
            tools_executed = [],
            partial_response = "",
            tool_count     = 0,
        )
        self._current  = snap
        self._tool_count = 0
        logger.debug(f"Snapshot: started {snap.snapshot_id}")
        return snap

    def record_tool(
        self,
        tool_name: str,
        args:      dict,
        result:    str,
    ) -> None:
        """Record a tool execution in the current snapshot."""
        if not self._current:
            return

        self._tool_count += 1
        self._current.tool_count = self._tool_count
        self._current.tools_executed.append({
            "tool":           tool_name,
            "args":           {k: str(v)[:50] for k, v in args.items()},
            "result_summary": result[:100],
            "timestamp":      datetime.now().isoformat(),
        })

        # Save snapshot every N tool calls
        if self._tool_count % self.SNAPSHOT_INTERVAL == 0:
            self._save()

    def update_phase(self, phase: str) -> None:
        """Update current execution phase."""
        if self._current:
            self._current.phase = phase

    def update_partial_response(self, text: str) -> None:
        """Update partial response in snapshot."""
        if self._current:
            self._current.partial_response = text[:500]

    def complete_turn(self) -> None:
        """Mark current turn as complete and save final snapshot."""
        if self._current:
            self._current.is_complete = True
            self._save()
            logger.debug(f"Snapshot: completed {self._current.snapshot_id}")
            self._current = None

    def _save(self) -> None:
        """Save current snapshot to disk."""
        if not self._current:
            return
        try:
            path = self.snapshot_dir / f"{self._current.snapshot_id}.json"
            path.write_text(json.dumps(asdict(self._current), indent=2))
            self._cleanup_old()
        except Exception as e:
            logger.debug(f"Snapshot save failed: {e}")

    def _cleanup_old(self) -> None:
        """Remove old snapshots beyond MAX_SNAPSHOTS."""
        snapshots = sorted(
            self.snapshot_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
        )
        for old in snapshots[:-self.MAX_SNAPSHOTS]:
            old.unlink(missing_ok=True)

    def get_latest_incomplete(self, session_key: str) -> RuntimeSnapshot | None:
        """Get latest incomplete snapshot for recovery."""
        snapshots = sorted(
            self.snapshot_dir.glob(f"{session_key}_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for snap_path in snapshots:
            try:
                data = json.loads(snap_path.read_text())
                if not data.get("is_complete"):
                    snap = RuntimeSnapshot(**data)
                    logger.info(
                        f"Snapshot: found incomplete snapshot {snap.snapshot_id} "
                        f"({snap.tool_count} tools executed, phase={snap.phase})"
                    )
                    return snap
            except Exception:
                continue
        return None

    def build_recovery_context(self, snapshot: RuntimeSnapshot) -> str:
        """Build recovery context string for injection into new session."""
        tools_summary = "\n".join(
            f"  - {t['tool']}({t['args']}) → {t['result_summary']}"
            for t in snapshot.tools_executed
        )
        return (
            f"[RECOVERY FROM SNAPSHOT {snapshot.snapshot_id}]\n"
            f"Original task: {snapshot.task}\n"
            f"Phase reached: {snapshot.phase}\n"
            f"Tools already executed ({snapshot.tool_count}):\n"
            f"{tools_summary}\n"
            f"Partial response: {snapshot.partial_response}\n"
            f"Resume from where execution stopped."
        )

    def get_stats(self) -> dict:
        """Return snapshot statistics."""
        all_snaps = list(self.snapshot_dir.glob("*.json"))
        incomplete = []
        for p in all_snaps:
            try:
                d = json.loads(p.read_text())
                if not d.get("is_complete"):
                    incomplete.append(p.name)
            except Exception:
                pass
        return {
            "total_snapshots": len(all_snaps),
            "incomplete":      len(incomplete),
            "snapshot_dir":    str(self.snapshot_dir),
        }
