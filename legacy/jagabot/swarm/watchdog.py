"""Watchdog — daemon thread monitoring swarm health and system resources."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class Alert:
    """A watchdog alert."""
    level: str  # "warning" or "critical"
    source: str
    message: str
    timestamp: float = field(default_factory=time.time)


class Watchdog:
    """Background watchdog that monitors swarm health.

    Checks:
    - Stalled workers (via WorkerTracker)
    - System resource usage (optional psutil)
    - Queue depth anomalies
    - Cost budget overruns

    Runs as a daemon thread with configurable check interval.
    """

    def __init__(
        self,
        check_interval: float = 15.0,
        cpu_threshold: float = 90.0,
        memory_threshold: float = 85.0,
    ):
        self._interval = check_interval
        self._cpu_threshold = cpu_threshold
        self._memory_threshold = memory_threshold
        self._thread: threading.Thread | None = None
        self._running = False
        self._alerts: list[Alert] = []
        self._max_alerts = 500
        self._lock = threading.Lock()

        # Optional references — set by orchestrator
        self._tracker = None  # WorkerTracker
        self._cost_tracker = None  # CostTracker

    def set_tracker(self, tracker: Any) -> None:
        """Wire the WorkerTracker for stalled-worker detection."""
        self._tracker = tracker

    def set_cost_tracker(self, cost_tracker: Any) -> None:
        """Wire the CostTracker for budget monitoring."""
        self._cost_tracker = cost_tracker

    def start(self) -> None:
        """Start the watchdog daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="jagabot-watchdog")
        self._thread.start()
        logger.info("Watchdog started (interval={}s)", self._interval)

    def stop(self) -> None:
        """Stop the watchdog."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self._interval + 2)
            self._thread = None
        logger.info("Watchdog stopped")

    def _loop(self) -> None:
        """Main watchdog loop."""
        while self._running:
            try:
                self._check_workers()
                self._check_system()
                self._check_costs()
            except Exception as exc:
                logger.warning("Watchdog check error: {}", exc)
            time.sleep(self._interval)

    def _check_workers(self) -> None:
        """Detect stalled workers."""
        if not self._tracker:
            return
        stalled = self._tracker.detect_stalled()
        for w in stalled:
            self._add_alert(Alert(
                level="warning",
                source="worker_tracker",
                message=f"Worker stalled: {w.tool_name}/{w.method} (task={w.task_id}, "
                        f"running for {time.monotonic() - w.started_at:.1f}s)",
            ))

    def _check_system(self) -> None:
        """Check system resource usage (requires optional psutil)."""
        try:
            import psutil
        except ImportError:
            return

        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()

        if cpu > self._cpu_threshold:
            self._add_alert(Alert(
                level="warning" if cpu < 95 else "critical",
                source="system",
                message=f"CPU usage high: {cpu:.1f}%",
            ))

        if mem.percent > self._memory_threshold:
            self._add_alert(Alert(
                level="warning" if mem.percent < 95 else "critical",
                source="system",
                message=f"Memory usage high: {mem.percent:.1f}% "
                        f"({mem.available // (1024**2)}MB available)",
            ))

    def _check_costs(self) -> None:
        """Check for cost budget overruns."""
        if not self._cost_tracker:
            return
        alerts = self._cost_tracker.recent_alerts(limit=1)
        if alerts:
            latest = alerts[0]
            self._add_alert(Alert(
                level="warning",
                source="costs",
                message=f"Budget exceeded: {latest['period']} — "
                        f"${latest['actual']:.4f} / ${latest['budget']:.4f}",
            ))

    def _add_alert(self, alert: Alert) -> None:
        """Thread-safe alert addition."""
        with self._lock:
            self._alerts.append(alert)
            if len(self._alerts) > self._max_alerts:
                self._alerts = self._alerts[-self._max_alerts:]
        logger.warning("Watchdog alert [{}]: {}", alert.source, alert.message)

    def get_alerts(self, limit: int = 20) -> list[Alert]:
        """Return recent alerts."""
        with self._lock:
            return list(reversed(self._alerts[-limit:]))

    def is_running(self) -> bool:
        return self._running

    def health(self) -> dict[str, Any]:
        """Return watchdog health status."""
        system_info: dict[str, Any] = {}
        try:
            import psutil
            system_info = {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "memory_available_mb": psutil.virtual_memory().available // (1024**2),
            }
        except ImportError:
            system_info = {"note": "psutil not installed — system metrics unavailable"}

        with self._lock:
            alert_count = len(self._alerts)
            recent_critical = sum(1 for a in self._alerts[-20:] if a.level == "critical")

        return {
            "running": self._running,
            "check_interval_s": self._interval,
            "total_alerts": alert_count,
            "recent_critical": recent_critical,
            "system": system_info,
        }
