"""
CalibrationEngine — Empirical Feedback Loop Phase 1

Builds calibration curves from verified outcomes.
Detects overconfidence/underconfidence patterns.
Updates BeliefEngine and MetaLearning with real accuracy data.

Flow:
  User verifies outcome (correct/wrong)
  → OutcomeTracker records to pending_outcomes.json
  → CalibrationEngine reads verified outcomes
  → Builds calibration curve (stated confidence vs actual accuracy)
  → Detects drift (is the agent getting worse?)
  → Updates BeliefEngine trust scores
  → Reports to MetaLearning

Calibration curve example:
  Confidence 90% → Actual accuracy 72% → Overconfident by 18%
  Confidence 70% → Actual accuracy 68% → Well calibrated
  Confidence 50% → Actual accuracy 45% → Slightly overconfident
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class CalibrationBucket:
    """One bucket of the calibration curve."""
    confidence_min: float
    confidence_max: float
    predictions:    int   = 0
    correct:        int   = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.predictions if self.predictions > 0 else 0.0

    @property
    def midpoint(self) -> float:
        return (self.confidence_min + self.confidence_max) / 2

    @property
    def calibration_error(self) -> float:
        """Positive = overconfident, negative = underconfident."""
        return self.midpoint - self.accuracy

    @property
    def label(self) -> str:
        err = self.calibration_error
        if abs(err) < 0.05:
            return "well_calibrated"
        elif err > 0.15:
            return "overconfident"
        elif err > 0.05:
            return "slightly_overconfident"
        elif err < -0.15:
            return "underconfident"
        else:
            return "slightly_underconfident"


@dataclass
class CalibrationReport:
    """Full calibration report for one session."""
    timestamp:       str
    total_outcomes:  int
    correct:         int
    accuracy:        float
    avg_confidence:  float
    calibration_error: float  # avg(confidence) - accuracy
    buckets:         list[CalibrationBucket]
    trend:           str      # "improving" | "stable" | "degrading"
    alert:           str      # warning message if calibration is poor


class CalibrationEngine:
    """
    Builds and tracks calibration curves from verified outcomes.
    """

    BUCKET_EDGES = [0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

    def __init__(self, workspace: Path):
        self.workspace    = Path(workspace)
        self.outcomes_path = self.workspace / "pending_outcomes.json"
        self.db_path      = self.workspace / "memory" / "calibration.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS calibration_snapshots (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    TEXT,
                total        INTEGER,
                correct      INTEGER,
                accuracy     REAL,
                avg_conf     REAL,
                cal_error    REAL,
                trend        TEXT,
                alert        TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS outcome_history (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key  TEXT,
                conclusion   TEXT,
                confidence   REAL,
                outcome      TEXT,
                correct      INTEGER,
                recorded_at  TEXT
            )
        """)
        conn.commit()
        conn.close()

    def load_verified_outcomes(self) -> list[dict]:
        """Load verified outcomes from pending_outcomes.json."""
        if not self.outcomes_path.exists():
            return []
        try:
            data = json.loads(self.outcomes_path.read_text())
            return [o for o in data if o.get("verified") and o.get("outcome")]
        except Exception as e:
            logger.debug(f"CalibrationEngine: could not load outcomes: {e}")
            return []

    def build_curve(self, outcomes: list[dict]) -> list[CalibrationBucket]:
        """Build calibration curve from verified outcomes."""
        buckets = []
        for i in range(len(self.BUCKET_EDGES) - 1):
            bucket = CalibrationBucket(
                confidence_min=self.BUCKET_EDGES[i],
                confidence_max=self.BUCKET_EDGES[i + 1],
            )
            for o in outcomes:
                conf = float(o.get("confidence", 0.5))
                if bucket.confidence_min <= conf < bucket.confidence_max:
                    bucket.predictions += 1
                    if o.get("outcome") == "correct":
                        bucket.correct += 1
            if bucket.predictions > 0:
                buckets.append(bucket)
        return buckets

    def detect_trend(self, window_days: int = 7) -> str:
        """Detect accuracy trend over recent period."""
        conn = sqlite3.connect(self.db_path)
        cutoff = (datetime.now() - timedelta(days=window_days)).isoformat()
        rows = conn.execute("""
            SELECT accuracy FROM calibration_snapshots
            WHERE timestamp > ? ORDER BY timestamp
        """, (cutoff,)).fetchall()
        conn.close()

        if len(rows) < 3:
            return "insufficient_data"

        accuracies = [r[0] for r in rows]
        first_half = sum(accuracies[:len(accuracies)//2]) / (len(accuracies)//2)
        second_half = sum(accuracies[len(accuracies)//2:]) / (len(accuracies) - len(accuracies)//2)

        diff = second_half - first_half
        if diff > 0.05:
            return "improving"
        elif diff < -0.05:
            return "degrading"
        return "stable"

    def generate_alert(
        self,
        accuracy: float,
        cal_error: float,
        trend: str,
    ) -> str:
        """Generate alert message if calibration is poor."""
        alerts = []
        if accuracy < 0.5:
            alerts.append(f"⚠️ Accuracy below 50% ({accuracy:.0%}) — worse than random")
        if cal_error > 0.2:
            alerts.append(f"⚠️ Overconfident by {cal_error:.0%} — reduce stated confidence")
        if cal_error < -0.2:
            alerts.append(f"⚠️ Underconfident by {abs(cal_error):.0%} — can state higher confidence")
        if trend == "degrading":
            alerts.append("⚠️ Performance trend: DEGRADING — review recent errors")
        return " | ".join(alerts) if alerts else "✅ Calibration nominal"

    def run(self) -> CalibrationReport | None:
        """Run full calibration analysis."""
        outcomes = self.load_verified_outcomes()
        if not outcomes:
            logger.debug("CalibrationEngine: no verified outcomes yet")
            return None

        total    = len(outcomes)
        correct  = sum(1 for o in outcomes if o.get("outcome") == "correct")
        accuracy = correct / total if total > 0 else 0.0
        avg_conf = sum(float(o.get("confidence", 0.5)) for o in outcomes) / total
        cal_err  = avg_conf - accuracy
        trend    = self.detect_trend()
        buckets  = self.build_curve(outcomes)
        alert    = self.generate_alert(accuracy, cal_err, trend)

        report = CalibrationReport(
            timestamp        = datetime.now().isoformat(),
            total_outcomes   = total,
            correct          = correct,
            accuracy         = round(accuracy, 3),
            avg_confidence   = round(avg_conf, 3),
            calibration_error = round(cal_err, 3),
            buckets          = buckets,
            trend            = trend,
            alert            = alert,
        )

        # Save snapshot
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO calibration_snapshots
            (timestamp, total, correct, accuracy, avg_conf, cal_error, trend, alert)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report.timestamp, total, correct, accuracy,
            avg_conf, cal_err, trend, alert
        ))
        conn.commit()
        conn.close()

        logger.info(
            f"CalibrationEngine: {accuracy:.0%} accuracy "
            f"({correct}/{total}) cal_error={cal_err:+.0%} "
            f"trend={trend} — {alert}"
        )
        return report

    def format_report(self, report: CalibrationReport) -> str:
        """Format calibration report for display."""
        lines = [
            f"## 📊 Calibration Report — {report.timestamp[:10]}",
            f"",
            f"**Accuracy:** {report.accuracy:.0%} ({report.correct}/{report.total_outcomes})",
            f"**Avg Confidence:** {report.avg_confidence:.0%}",
            f"**Calibration Error:** {report.calibration_error:+.0%} "
            f"({'overconfident' if report.calibration_error > 0 else 'underconfident'})",
            f"**Trend:** {report.trend}",
            f"**Alert:** {report.alert}",
            f"",
            f"### Calibration Curve",
        ]
        for b in report.buckets:
            bar = "█" * int(b.accuracy * 10) + "░" * (10 - int(b.accuracy * 10))
            lines.append(
                f"  {b.confidence_min:.0%}-{b.confidence_max:.0%} conf → "
                f"b.accuracy:.0%} actual [{bar}] {b.label}"
            )
        return "\n".join(lines)

    def get_confidence_adjustment(self, stated_confidence: float) -> float:
        """
        Adjust stated confidence based on calibration history.
        If agent says 90% but historically only 72% accurate at that level,
        return adjusted confidence of 72%.
        """
        outcomes = self.load_verified_outcomes()
        if not outcomes:
            return stated_confidence

        # Find relevant bucket
        for i in range(len(self.BUCKET_EDGES) - 1):
            if self.BUCKET_EDGES[i] <= stated_confidence < self.BUCKET_EDGES[i + 1]:
                bucket_outcomes = [
                    o for o in outcomes
                    if self.BUCKET_EDGES[i] <= float(o.get("confidence", 0.5)) < self.BUCKET_EDGES[i + 1]
                ]
                if len(bucket_outcomes) >= 5:  # Need minimum data
                    bucket_correct = sum(1 for o in bucket_outcomes if o.get("outcome") == "correct")
                    adjusted = bucket_correct / len(bucket_outcomes)
                    if abs(adjusted - stated_confidence) > 0.1:
                        logger.debug(
                            f"CalibrationEngine: adjusted {stated_confidence:.0%} → {adjusted:.0%} "
                            f"(based on {len(bucket_outcomes)} outcomes)"
                        )
                    return adjusted
        return stated_confidence
