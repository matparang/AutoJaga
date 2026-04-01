"""
BDI Scorecard — Strategic Autonomy Scoring for Agent Turns.

Scores each task turn on 4 dimensions:
  - Belief monitoring  (did agent verify assumptions?)
  - Desire persistence (did agent recover from failures?)
  - Intention quality  (did agent use tools effectively?)
  - Anomaly handling   (did agent avoid chaotic behavior?)

Score range: 0-10
Target:      6+ = Autonomous Strategist
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json


@dataclass
class BDIScore:
    """Single turn BDI score."""
    timestamp:       str   = ""
    belief_score:    float = 0.0   # 0-2.5: verified assumptions
    desire_score:    float = 0.0   # 0-2.5: maintained goal despite failures
    intention_score: float = 0.0   # 0-2.5: effective tool use
    anomaly_score:   float = 0.0   # 0-2.5: clean execution
    total:           float = 0.0   # 0-10
    label:           str   = ""    # "Reactive" | "Emerging" | "Autonomous"
    notes:           list  = field(default_factory=list)


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
        quality:       response quality score (0-1)
        anomaly_count: behavior anomaly count
        tool_errors:   number of tool call failures this turn
        used_fallback: did agent recover and try alternative approach?
        verified_mid:  did agent verify assumptions mid-task?
    """
    score = BDIScore(timestamp=datetime.now().isoformat())
    notes = []

    # ── Belief Score (0-2.5) ─────────────────────────────────────────
    belief_tools = {"read_file", "web_search"}
    belief_used = bool(set(tools_used) & belief_tools)

    if verified_mid:
        score.belief_score = 2.5
        notes.append("✅ Belief: mid-task verification")
    elif belief_used and quality >= 0.7:
        score.belief_score = 1.5
        notes.append("🟡 Belief: used info sources")
    elif belief_used:
        score.belief_score = 1.0
        notes.append("🟠 Belief: info sourced but quality low")
    else:
        score.belief_score = 0.5
        notes.append("❌ Belief: no verification")

    # ── Desire Score (0-2.5) ─────────────────────────────────────────
    if tool_errors > 0 and used_fallback and quality >= 0.6:
        score.desire_score = 2.5
        notes.append(f"✅ Desire: recovered from {tool_errors} error(s)")
    elif tool_errors > 0 and used_fallback:
        score.desire_score = 1.5
        notes.append("🟡 Desire: tried fallback but result weak")
    elif tool_errors == 0 and quality >= 0.7:
        score.desire_score = 2.0
        notes.append("✅ Desire: clean execution, goal reached")
    elif tool_errors > 0:
        score.desire_score = 0.5
        notes.append(f"❌ Desire: {tool_errors} error(s), no recovery")
    else:
        score.desire_score = 1.0
        notes.append("🟠 Desire: no errors but quality low")

    # ── Intention Score (0-2.5) ─────────────────────────────────────
    tool_count = len(tools_used)
    unique_tools = len(set(tools_used))

    if tool_count >= 3 and unique_tools >= 2 and quality >= 0.7:
        score.intention_score = 2.5
        notes.append(f"✅ Intention: {tool_count} calls, {unique_tools} tools")
    elif tool_count >= 1 and quality >= 0.7:
        score.intention_score = 2.0
        notes.append(f"✅ Intention: effective tool use")
    elif tool_count >= 1:
        score.intention_score = 1.0
        notes.append("🟠 Intention: tools used but weak result")
    else:
        score.intention_score = 0.5
        notes.append("❌ Intention: no tools used")

    # ── Anomaly Score (0-2.5) ─────────────────────────────────────
    if anomaly_count == 0:
        score.anomaly_score = 2.5
        notes.append("✅ Anomaly: clean execution")
    elif anomaly_count <= 2:
        score.anomaly_score = 1.5
        notes.append(f"🟡 Anomaly: {anomaly_count} minor issue(s)")
    else:
        score.anomaly_score = 0.5
        notes.append(f"❌ Anomaly: {anomaly_count} behavior anomalies")

    # ── Total ────────────────────────────────────────────────────────
    score.total = round(
        score.belief_score + score.desire_score + 
        score.intention_score + score.anomaly_score, 1
    )

    if score.total >= 8:
        score.label = "Autonomous Strategist"
    elif score.total >= 6:
        score.label = "Emerging Agent"
    else:
        score.label = "Reactive Script"

    score.notes = notes
    return score


class BDIScorecardTracker:
    """Tracks BDI scores across sessions."""
    
    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self.scores_file = self.workspace / "memory" / "bdi_scores.json"
        self.scores_file.parent.mkdir(parents=True, exist_ok=True)
        self._scores: list[dict] = []
        self._load()
    
    def _load(self) -> None:
        """Load existing scores."""
        if self.scores_file.exists():
            try:
                self._scores = json.loads(self.scores_file.read_text())
            except Exception:
                self._scores = []
    
    def _save(self) -> None:
        """Save scores to disk."""
        self.scores_file.write_text(json.dumps(self._scores[-100:], indent=2))
    
    def record(self, score: BDIScore) -> None:
        """Record a BDI score."""
        self._scores.append({
            "timestamp": score.timestamp,
            "belief": score.belief_score,
            "desire": score.desire_score,
            "intention": score.intention_score,
            "anomaly": score.anomaly_score,
            "total": score.total,
            "label": score.label,
            "notes": score.notes,
        })
        self._save()
    
    def get_average(self, last_n: int = 10) -> float:
        """Get average score over last N turns."""
        recent = self._scores[-last_n:]
        if not recent:
            return 0.0
        return sum(s["total"] for s in recent) / len(recent)
    
    def get_trend(self) -> str:
        """Get trend direction."""
        if len(self._scores) < 5:
            return "insufficient_data"
        
        recent = self.get_average(5)
        older = sum(s["total"] for s in self._scores[-10:-5]) / 5 if len(self._scores) >= 10 else recent
        
        if recent > older + 0.5:
            return "improving"
        elif recent < older - 0.5:
            return "declining"
        return "stable"
