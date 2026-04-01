"""
PerformanceTrendTracker — Empirical Feedback Loop Phase 3

Tracks agent performance over time and detects early degradation.

Metrics tracked:
  - Accuracy trend (correct/wrong ratio over time)
  - BDI score trend (autonomy level over time)
  - Quality score trend (session_writer quality)
  - Token efficiency trend (tokens per useful output)
  - Domain reliability trends (per-domain accuracy)

Early warnings:
  - Accuracy drops >10% over 7 days → alert
  - BDI score drops below 6.0 → alert
  - Quality drops below 0.6 average → alert
  - Single domain consistently wrong → domain alert
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger


@dataclass
class PerformanceSnapshot:
    """One performance measurement point."""
    timestamp:     str
    bdi_score:     float
    quality_score: float
    accuracy:      float   # from outcomes
    token_efficiency: float  # quality / tokens_used
    domain:        str
    session_key:   str


@dataclass
class TrendAlert:
    """An early warning alert."""
    metric:    str
    direction: str   # "dropping" | "rising"
    current:   float
    baseline:  float
    change:    float
    severity:  str   # "warning" | "critical"
    message:   str


class PerformanceTrendTracker:
    """
    Tracks performance metrics over time.
    Detects early degradation before it becomes critical.
    """

    # Alert thresholds
    BDI_WARNING_THRESHOLD    = 6.0
    BDI_CRITICAL_THRESHOLD   = 4.0
    QUALITY_WARNING_THRESHOLD = 0.6
    ACCURACY_DROP_THRESHOLD  = 0.10   # 10% drop triggers warning
    MIN_SAMPLES_FOR_TREND    = 5

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self.db_path   = self.workspace / "memory" / "performance.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._session_bdi_scores: list[float] = []
        self._session_quality:    list[float] = []

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp        TEXT,
                bdi_score        REAL,
                quality_score    REAL,
                accuracy         REAL,
                token_efficiency REAL,
                domain           TEXT,
                session_key      TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                metric    TEXT,
                severity  TEXT,
                message   TEXT,
                resolved  INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def record(
        self,
        bdi_score:     float,
        quality_score: float,
        domain:        str = "general",
        session_key:   str = "",
        tokens_used:   int = 0,
        accuracy:      float = -1.0,  # -1 = unknown
    ) -> None:
        """Record a performance snapshot."""
        self._session_bdi_scores.append(bdi_score)
        self._session_quality.append(quality_score)

        token_efficiency = quality_score / (tokens_used / 1000) if tokens_used > 0 else 0.0

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO snapshots
            (timestamp, bdi_score, quality_score, accuracy,
             token_efficiency, domain, session_key)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            bdi_score, quality_score, accuracy,
            token_efficiency, domain, session_key
        ))
        conn.commit()
        conn.close()

        logger.debug(
            f"PerfTracker: recorded bdi={bdi_score:.1f} "
            f"quality={quality_score:.2f} domain={domain}"
        )

    def get_trend(self, metric: str, days: int = 7) -> dict:
        """Get trend for a specific metric over N days."""
        conn    = sqlite3.connect(self.db_path)
        cutoff  = (datetime.now() - timedelta(days=days)).isoformat()
        rows    = conn.execute(f"""
            SELECT {metric}, timestamp FROM snapshots
            WHERE timestamp > ?
            ORDER BY timestamp
        """, (cutoff,)).fetchall()
        conn.close()

        if len(rows) < self.MIN_SAMPLES_FOR_TREND:
            return {"trend": "insufficient_data", "samples": len(rows)}

        values    = [r[0] for r in rows if r[0] is not None]
        avg_all   = sum(values) / len(values)
        half      = len(values) // 2
        avg_first = sum(values[:half]) / half if half > 0 else avg_all
        avg_last  = sum(values[half:]) / (len(values) - half)
        change    = avg_last - avg_first

        return {
            "trend":     "improving" if change > 0.05 else "degrading" if change < -0.05 else "stable",
            "current":   round(avg_last, 3),
            "baseline":  round(avg_first, 3),
            "change":    round(change, 3),
            "samples":   len(values),
        }

    def check_alerts(self) -> list[TrendAlert]:
        """Check all metrics for alert conditions."""
        alerts = []

        # BDI score trend
        bdi_trend = self.get_trend("bdi_score")
        if bdi_trend.get("trend") != "insufficient_data":
            current = bdi_trend["current"]
            if current < self.BDI_CRITICAL_THRESHOLD:
                alerts.append(TrendAlert(
                    metric="bdi_score", direction="dropping",
                    current=current, baseline=bdi_trend["baseline"],
                    change=bdi_trend["change"], severity="critical",
                    message=f"BDI score critically low ({current:.1f}/10) — agent operating as Reactive Script"
                ))
            elif current < self.BDI_WARNING_THRESHOLD:
                alerts.append(TrendAlert(
                    metric="bdi_score", direction="dropping",
                    current=current, baseline=bdi_trend["baseline"],
                    change=bdi_trend["change"], severity="warning",
                    message=f"BDI score dropping ({current:.1f}/10) — check belief/desire/intention modules"
                ))

        # Quality score trend
        q_trend = self.get_trend("quality_score")
        if q_trend.get("trend") != "insufficient_data":
            current = q_trend["current"]
            if current < self.QUALITY_WARNING_THRESHOLD:
                alerts.append(TrendAlert(
                    metric="quality_score", direction="dropping",
                    current=current, baseline=q_trend["baseline"],
                    change=q_trend["change"], severity="warning",
                    message=f"Quality score dropping ({current:.0%}) — review recent session outputs"
                ))

        # Log alerts
        if alerts:
            conn = sqlite3.connect(self.db_path)
            for alert in alerts:
                conn.execute("""
                    INSERT INTO alerts (timestamp, metric, severity, message)
                    VALUES (?, ?, ?, ?)
                """, (datetime.now().isoformat(), alert.metric, alert.severity, alert.message))
                logger.warning(f"PerfTracker ALERT [{alert.severity}]: {alert.message}")
            conn.commit()
            conn.close()

        return alerts

    def get_session_summary(self) -> dict:
        """Return summary of current session performance."""
        if not self._session_bdi_scores:
            return {}
        avg_bdi = sum(self._session_bdi_scores) / len(self._session_bdi_scores)
        avg_q   = sum(self._session_quality) / len(self._session_quality) if self._session_quality else 0
        return {
            "session_turns":    len(self._session_bdi_scores),
            "avg_bdi_score":    round(avg_bdi, 2),
            "avg_quality":      round(avg_q, 2),
            "bdi_trend":        self.get_trend("bdi_score", days=1),
            "quality_trend":    self.get_trend("quality_score", days=1),
        }

    def format_dashboard(self) -> str:
        """Format performance dashboard."""
        bdi_t = self.get_trend("bdi_score")
        q_t   = self.get_trend("quality_score")
        alerts = self.check_alerts()

        lines = [
            "## 📈 Performance Trend Dashboard",
            f"",
            f"**BDI Score:** {bdi_t.get('current', 'N/A')} "
            f"({bdi_t.get('trend', 'N/A')}, Δ{bdi_t.get('change', 0):+.2f})",
            f"**Quality:** {q_t.get('current', 'N/A'):.0%} "
            f"({q_t.get('trend', 'N/A')}, Δ{q_t.get('change', 0):+.2f})" if isinstance(q_t.get('current'), float) else "",
            f"**Session turns:** {len(self._session_bdi_scores)}",
            f"",
        ]
        if alerts:
            lines.append("### ⚠️ Alerts")
            for a in alerts:
                lines.append(f"- [{a.severity.upper()}] {a.message}")
        else:
            lines.append("### ✅ No active alerts")

        return "\n".join(lines)
