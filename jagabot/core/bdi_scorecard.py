"""
BDI Strategic Autonomy Scorecard

Scores each task turn on 4 dimensions:
  - Belief monitoring  (did agent verify assumptions?)
  - Desire persistence (did agent recover from failures?)
  - Intention quality  (did agent use tools effectively?)
  - Anomaly handling   (did agent avoid chaotic behavior?)

Score range: 0-10
Target:      6+ = Autonomous Strategist
Current:     2-4 = Reactive Script
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
from loguru import logger


@dataclass
class BDIScore:
    """Single turn BDI score."""
    timestamp:          str   = ""
    belief_score:       float = 0.0   # 0-2.5: verified assumptions
    desire_score:       float = 0.0   # 0-2.5: maintained goal despite failures
    intention_score:    float = 0.0   # 0-2.5: effective tool use
    anomaly_score:      float = 0.0   # 0-2.5: clean execution
    total:              float = 0.0   # 0-10
    label:              str   = ""    # "Reactive Script" | "Emerging" | "Autonomous"
    notes:              list  = field(default_factory=list)


def score_turn(
    tools_used:     list[str],
    quality:        float,
    anomaly_count:  int,
    tool_errors:    int   = 0,
    used_fallback:  bool  = False,
    verified_mid:   bool  = False,
) -> BDIScore:
    """
    Score a single agent turn on BDI dimensions.

    Args:
        tools_used:    list of tool names used this turn
        quality:       session_writer quality score (0-1)
        anomaly_count: behavior monitor anomaly count
        tool_errors:   number of tool call failures this turn
        used_fallback: did agent recover and try alternative approach?
        verified_mid:  did agent verify assumptions mid-task?
    """
    score = BDIScore(timestamp=datetime.now().isoformat())
    notes = []

    # ── Belief Score (0-2.5) ─────────────────────────────────────────
    # Did agent verify assumptions? Used self_model or memory checks?
    belief_tools = {"self_model_awareness", "memory_fleet", "read_file"}
    belief_used = bool(set(tools_used) & belief_tools)

    if verified_mid:
        score.belief_score = 2.5
        notes.append("✅ Belief: mid-task verification detected")
    elif belief_used and quality >= 0.7:
        score.belief_score = 1.5
        notes.append("🟡 Belief: used memory/self-model but no explicit verification")
    elif belief_used:
        score.belief_score = 1.0
        notes.append("🟠 Belief: checked memory but quality low")
    else:
        score.belief_score = 0.5
        notes.append("❌ Belief: no assumption verification")

    # ── Desire Score (0-2.5) ─────────────────────────────────────────
    # Did agent maintain goal when things went wrong?
    if used_fallback:
        score.desire_score = 2.5
        notes.append("✅ Desire: used alternative approach after failure")
    elif tool_errors > 0 and quality >= 0.7:
        score.desire_score = 1.5
        notes.append("🟡 Desire: recovered from tool errors, achieved goal")
    elif tool_errors > 0 and quality < 0.7:
        score.desire_score = 0.5
        notes.append("❌ Desire: tool errors led to goal failure")
    else:
        score.desire_score = 1.5  # No errors = smooth execution
        notes.append("🟢 Desire: clean execution, no failures to recover from")

    # ── Intention Score (0-2.5) ──────────────────────────────────────
    # Did agent use tools effectively and purposefully?
    n_tools = len(set(tools_used))  # unique tools used

    if n_tools >= 3 and quality >= 0.8:
        score.intention_score = 2.5
        notes.append("✅ Intention: diverse tool use, high quality output")
    elif n_tools >= 2 and quality >= 0.7:
        score.intention_score = 2.0
        notes.append("🟡 Intention: good tool use")
    elif n_tools >= 1 and quality >= 0.6:
        score.intention_score = 1.5
        notes.append("🟠 Intention: minimal tool use")
    elif n_tools == 0:
        score.intention_score = 0.5
        notes.append("❌ Intention: no tools used")
    else:
        score.intention_score = 1.0
        notes.append("🟠 Intention: tools used but quality low")

    # ── Anomaly Score (0-2.5) ────────────────────────────────────────
    # Did agent execute cleanly without behavior anomalies?
    if anomaly_count == 0:
        score.anomaly_score = 2.5
        notes.append("✅ Execution: clean, no anomalies")
    elif anomaly_count == 1:
        score.anomaly_score = 1.5
        notes.append("🟡 Execution: 1 anomaly detected")
    elif anomaly_count == 2:
        score.anomaly_score = 0.5
        notes.append("🟠 Execution: 2 anomalies detected")
    else:
        score.anomaly_score = 0.0
        notes.append("❌ Execution: multiple anomalies — chaotic behavior")

    # ── Total + Label ─────────────────────────────────────────────────
    score.total = round(
        score.belief_score +
        score.desire_score +
        score.intention_score +
        score.anomaly_score, 2
    )
    score.notes = notes

    if score.total >= 8:
        score.label = "Autonomous Strategist"
    elif score.total >= 6:
        score.label = "Emerging Autonomy"
    elif score.total >= 4:
        score.label = "Semi-Reactive"
    else:
        score.label = "Reactive Script"

    logger.info(
        f"BDI Score: {score.total:.1f}/10 ({score.label}) "
        f"B={score.belief_score} D={score.desire_score} "
        f"I={score.intention_score} A={score.anomaly_score}"
    )

    return score


class BDIScorecardTracker:
    """
    Tracks BDI scores over time.
    Stores history in workspace/memory/bdi_scores.jsonl
    """

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self.db_path = self.workspace / "memory" / "bdi_scores.jsonl"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._recent: list[BDIScore] = []

    def record(self, score: BDIScore) -> None:
        """Save score to disk and keep in memory."""
        self._recent.append(score)
        if len(self._recent) > 50:
            self._recent = self._recent[-50:]

        with open(self.db_path, "a") as f:
            f.write(json.dumps({
                "timestamp":       score.timestamp,
                "total":           score.total,
                "label":           score.label,
                "belief_score":    score.belief_score,
                "desire_score":    score.desire_score,
                "intention_score": score.intention_score,
                "anomaly_score":   score.anomaly_score,
                "notes":           score.notes,
            }) + "\n")

    def get_avg_score(self, last_n: int = 10) -> float:
        """Return average BDI score over last N turns."""
        recent = self._recent[-last_n:]
        if not recent:
            return 0.0
        return round(sum(s.total for s in recent) / len(recent), 2)

    def get_trend(self) -> str:
        """Return trend: improving / declining / stable."""
        if len(self._recent) < 4:
            return "insufficient data"
        first_half = self._recent[-4:-2]
        second_half = self._recent[-2:]
        avg_first = sum(s.total for s in first_half) / 2
        avg_second = sum(s.total for s in second_half) / 2
        diff = avg_second - avg_first
        if diff > 0.5:
            return "improving"
        elif diff < -0.5:
            return "declining"
        return "stable"

    def get_summary(self) -> dict:
        """Return current BDI health summary."""
        return {
            "avg_score":    self.get_avg_score(),
            "trend":        self.get_trend(),
            "total_turns":  len(self._recent),
            "latest_label": self._recent[-1].label if self._recent else "no data",
        }
