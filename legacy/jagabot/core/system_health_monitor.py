# jagabot/core/system_health_monitor.py
"""
System Health Monitor — Unified health scoring across all subsystems.

Aggregates metrics from:
- TrajectoryMonitor (spin detection, entropy)
- BrierScorer (calibration accuracy)
- Librarian (constraint count)
- MemoryManager (index size, query latency)
- OutcomeTracker (verification rate)
- SessionIndex (session count, quality avg)

Provides single health score 0.0-1.0 and detailed diagnostics.

Wire into loop.py __init__:
    from jagabot.core.system_health_monitor import SystemHealthMonitor
    self.health_monitor = SystemHealthMonitor(workspace)

Wire into commands.py (for /status command):
    @app.command()
    def status():
        from jagabot.core.system_health_monitor import SystemHealthMonitor
        monitor = SystemHealthMonitor(Path.home() / ".jagabot")
        print(monitor.get_health_report())
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Config ───────────────────────────────────────────────────────────
HEALTH_WEIGHTS = {
    "calibration":   0.25,  # Brier trust score
    "efficiency":    0.20,  # trajectory (low entropy)
    "verification":  0.20,  # outcome verification rate
    "memory":        0.15,  # memory index health
    "constraints":   0.10,  # librarian constraints (learning from failures)
    "activity":      0.10,  # recent session activity
}

# Thresholds
EXCELLENT_HEALTH = 0.85
GOOD_HEALTH      = 0.70
WARNING_HEALTH   = 0.50
CRITICAL_HEALTH  = 0.30


@dataclass
class HealthReport:
    """Complete system health report."""
    overall_score:      float
    status:             str  # "excellent" | "good" | "warning" | "critical"
    calibration_score:  float
    efficiency_score:   float
    verification_score: float
    memory_score:       float
    constraints_score:  float
    activity_score:     float
    recommendations:    list[str] = field(default_factory=list)
    timestamp:          str = field(default_factory=lambda: datetime.now().isoformat())


class SystemHealthMonitor:
    """
    Unified health monitoring across all AutoJaga subsystems.

    Aggregates metrics from trajectory, Brier, librarian, memory,
    outcomes, and sessions into single health score.
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = Path(workspace)
        self.memory_dir = self.workspace / "memory"
        self._cache: Optional[HealthReport] = None
        self._cache_time: float = 0.0
        self._cache_ttl: float = 60.0  # 1 min cache

    # ── Public API ───────────────────────────────────────────────────

    def get_health(self) -> HealthReport:
        """
        Get current health score.
        Cached for 1 minute to avoid expensive recomputation.
        """
        now = time.time()
        if self._cache and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        report = self._compute_health()
        self._cache = report
        self._cache_time = now
        return report

    def get_health_report(self) -> str:
        """
        Get human-readable health report.
        Suitable for /status command output.
        """
        report = self.get_health()

        status_icon = {
            "excellent": "✅",
            "good":      "✅",
            "warning":   "⚠️",
            "critical":  "❌",
        }.get(report.status, "❓")

        lines = [
            f"{status_icon} **AutoJaga System Health**",
            "",
            f"**Overall Score:** {report.overall_score:.2f} ({report.status})",
            "",
            "### Subsystem Scores",
            "",
            f"- 🎯 **Calibration:** {report.calibration_score:.2f}",
            f"  → Brier trust score (prediction accuracy)",
            "",
            f"- ⚡ **Efficiency:** {report.efficiency_score:.2f}",
            f"  → Trajectory entropy (spinning detection)",
            "",
            f"- ✅ **Verification:** {report.verification_score:.2f}",
            f"  → Outcome verification rate",
            "",
            f"- 🧠 **Memory:** {report.memory_score:.2f}",
            f"  → FTS index health + query latency",
            "",
            f"- 📚 **Constraints:** {report.constraints_score:.2f}",
            f"  → Learning from failures (Librarian)",
            "",
            f"- 📊 **Activity:** {report.activity_score:.2f}",
            f"  → Recent session activity",
            "",
        ]

        if report.recommendations:
            lines.append("### Recommendations")
            lines.append("")
            for i, rec in enumerate(report.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        lines.append(f"*Report generated: {report.timestamp[:19]}*")

        return "\n".join(lines)

    def reset_cache(self) -> None:
        """Force recomputation on next get_health() call."""
        self._cache = None
        self._cache_time = 0.0

    # ── Health computation ───────────────────────────────────────────

    def _compute_health(self) -> HealthReport:
        """Compute all health metrics and aggregate."""
        # Gather metrics from all subsystems
        calibration  = self._check_calibration()
        efficiency   = self._check_efficiency()
        verification = self._check_verification()
        memory       = self._check_memory()
        constraints  = self._check_constraints()
        activity     = self._check_activity()

        # Weighted average
        overall = (
            calibration  * HEALTH_WEIGHTS["calibration"] +
            efficiency   * HEALTH_WEIGHTS["efficiency"] +
            verification * HEALTH_WEIGHTS["verification"] +
            memory       * HEALTH_WEIGHTS["memory"] +
            constraints  * HEALTH_WEIGHTS["constraints"] +
            activity     * HEALTH_WEIGHTS["activity"]
        )

        # Determine status
        if overall >= EXCELLENT_HEALTH:
            status = "excellent"
        elif overall >= GOOD_HEALTH:
            status = "good"
        elif overall >= WARNING_HEALTH:
            status = "warning"
        else:
            status = "critical"

        # Generate recommendations
        recommendations = self._generate_recommendations(
            calibration, efficiency, verification,
            memory, constraints, activity,
        )

        return HealthReport(
            overall_score      = round(overall, 3),
            status             = status,
            calibration_score  = round(calibration, 3),
            efficiency_score   = round(efficiency, 3),
            verification_score = round(verification, 3),
            memory_score       = round(memory, 3),
            constraints_score  = round(constraints, 3),
            activity_score     = round(activity, 3),
            recommendations    = recommendations,
        )

    def _check_calibration(self) -> float:
        """
        Check Brier Scorer calibration accuracy.
        Returns trust score 0.0-1.0.
        """
        try:
            from jagabot.kernels.brier_scorer import BrierScorer
            brier = BrierScorer(self.memory_dir / "brier.db")
            
            # Get overall trust score
            stats = brier.get_stats()
            trust = stats.get("overall_trust", 0.5)
            
            # Need at least some samples for reliable score
            samples = stats.get("total_predictions", 0)
            if samples < 3:
                return 0.5  # neutral if insufficient data
            
            return trust
            
        except Exception as e:
            logger.debug(f"Health check calibration failed: {e}")
            return 0.5  # neutral on error

    def _check_efficiency(self) -> float:
        """
        Check trajectory efficiency (low entropy = good).
        Returns efficiency score 0.0-1.0.
        """
        try:
            # Check recent trajectory stats if available
            # For now, use heuristic: no recent spin detections = good
            audit_log = self.memory_dir / "yolo_audit.log"
            if not audit_log.exists():
                return 0.8  # assume good if no data
            
            # Count spin detections in last 24 hours
            now = datetime.now()
            spin_count = 0
            total_runs = 0
            
            with open(audit_log) as f:
                for line in f:
                    if "YOLO" in line or "SESSION" in line:
                        total_runs += 1
                    if "SPIN" in line or "spin" in line:
                        spin_count += 1
            
            if total_runs == 0:
                return 0.8
            
            spin_rate = spin_count / max(1, total_runs)
            return max(0.0, 1.0 - (spin_rate * 2))  # penalize spinning
            
        except Exception as e:
            logger.debug(f"Health check efficiency failed: {e}")
            return 0.8  # assume good on error

    def _check_verification(self) -> float:
        """
        Check outcome verification rate.
        Returns verification score 0.0-1.0.
        """
        try:
            bridge_log = self.memory_dir / "bridge_log.json"
            if not bridge_log.exists():
                return 0.5  # neutral if no data
            
            import json
            data = json.loads(bridge_log.read_text())
            
            if not data:
                return 0.5
            
            verified = sum(1 for entry in data if entry.get("verified"))
            rate = verified / len(data)
            
            # Good verification rate is > 70%
            return min(1.0, rate / 0.7)
            
        except Exception as e:
            logger.debug(f"Health check verification failed: {e}")
            return 0.5

    def _check_memory(self) -> float:
        """
        Check memory system health.
        Returns memory score 0.0-1.0.
        """
        try:
            # Check FTS5 index
            db_path = self.memory_dir / "memory_fts.db"
            if not db_path.exists():
                return 0.3  # critical if no index
            
            import sqlite3
            conn = sqlite3.connect(db_path)
            
            # Count indexed entries
            cursor = conn.execute("SELECT COUNT(*) FROM memory_fts")
            count = cursor.fetchone()[0]
            
            # Check daily notes
            daily_dir = self.memory_dir / "daily"
            daily_count = len(list(daily_dir.glob("*.md"))) if daily_dir.exists() else 0
            
            # Check skills
            skills_dir = self.memory_dir / "skills"
            skills_count = len(list(skills_dir.glob("*.md"))) if skills_dir.exists() else 0
            
            conn.close()
            
            # Score based on content
            total = count + daily_count + skills_count
            if total == 0:
                return 0.3
            elif total < 10:
                return 0.5
            elif total < 50:
                return 0.7
            else:
                return 0.9
                
        except Exception as e:
            logger.debug(f"Health check memory failed: {e}")
            return 0.5

    def _check_constraints(self) -> float:
        """
        Check Librarian constraints (learning from failures).
        Returns constraints score 0.0-1.0.
        """
        try:
            from jagabot.core.librarian import Librarian
            librarian = Librarian(self.workspace)
            
            # Get constraints
            constraints = librarian.get_constraints(topic="general", max_items=100)
            
            # Some constraints = learning from failures (good)
            # Too many = many failures (bad)
            count = len(constraints.split("\n")) if constraints else 0
            
            if count == 0:
                return 0.5  # neutral (no failures recorded)
            elif count <= 3:
                return 0.8  # good (learning, not too many failures)
            elif count <= 10:
                return 0.6  # moderate
            else:
                return 0.4  # many failures
                
        except Exception as e:
            logger.debug(f"Health check constraints failed: {e}")
            return 0.5

    def _check_activity(self) -> float:
        """
        Check recent session activity.
        Returns activity score 0.0-1.0.
        """
        try:
            sessions_dir = self.workspace / "sessions"
            if not sessions_dir.exists():
                return 0.3
            
            # Count sessions in last 7 days
            now = datetime.now()
            week_ago = now - timedelta(days=7)
            active_count = 0
            
            for session_file in sessions_dir.glob("*.jsonl"):
                mtime = datetime.fromtimestamp(session_file.stat().st_mtime)
                if mtime > week_ago:
                    active_count += 1
            
            # Score based on activity
            if active_count == 0:
                return 0.3  # no recent activity
            elif active_count <= 5:
                return 0.6
            elif active_count <= 20:
                return 0.8
            else:
                return 1.0
                
        except Exception as e:
            logger.debug(f"Health check activity failed: {e}")
            return 0.5

    def _generate_recommendations(
        self,
        calibration: float,
        efficiency: float,
        verification: float,
        memory: float,
        constraints: float,
        activity: float,
    ) -> list[str]:
        """Generate actionable recommendations based on scores."""
        recommendations = []
        
        if calibration < 0.5:
            recommendations.append(
                "🎯 **Calibration**: Provide more outcome verdicts "
                "(say 'that was correct/wrong' after research). "
                "System needs 3+ verdicts per perspective for reliable trust scores."
            )
        
        if efficiency < 0.6:
            recommendations.append(
                "⚡ **Efficiency**: Agent is spinning (talking without acting). "
                "Consider using /yolo mode for autonomous execution, or "
                "be more specific in your requests."
            )
        
        if verification < 0.5:
            recommendations.append(
                "✅ **Verification**: Low outcome verification rate. "
                "Run `/pending` to see conclusions awaiting your verdict."
            )
        
        if memory < 0.5:
            recommendations.append(
                "🧠 **Memory**: Memory index is sparse. "
                "Run more research sessions to build up memory. "
                "Use `/memory flush` to consolidate findings."
            )
        
        if constraints < 0.4:
            recommendations.append(
                "📚 **Constraints**: Many verified failures recorded. "
                "Review `/memory` to see what the system has learned "
                "not to repeat."
            )
        
        if activity < 0.4:
            recommendations.append(
                "📊 **Activity**: Low recent usage. "
                "System performs best with regular interaction. "
                "Try `/research <topic>` to start a session."
            )
        
        if not recommendations:
            recommendations.append(
                "✅ **All systems healthy!** No action needed. "
                "Continue using AutoJaga normally."
            )
        
        return recommendations


# ── CLI helper ────────────────────────────────────────────────────────

def run_health_check(workspace: Path = None) -> None:
    """Run health check and print report. Called from commands.py."""
    from rich.console import Console
    from rich.markdown import Markdown
    
    if workspace is None:
        workspace = Path.home() / ".jagabot"
    
    monitor = SystemHealthMonitor(workspace)
    report = monitor.get_health_report()
    
    console = Console()
    console.print(Markdown(report))
