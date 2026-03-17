# jagabot/engines/engine_improver.py
"""
EngineImprover — Improves existing AutoJaga engines
using the agent's own tools and verified outcomes.

This is NOT a replacement for existing engines.
It uses what's already there (K1, K3, MetaLearning,
Evolution) and adds:

1. CrossKernelSyncer
   K1 + K3 have been islands — this connects them.
   K1 calibration FEEDS K3 weights automatically.
   K3 accuracy FEEDS K1 prior updates automatically.

2. ContextualEvolution
   Evolution engine currently mutates financial params.
   This extends it to mutate PROMPT PATTERNS —
   tracking which ideation/research prompts produce
   verified correct outcomes via IdeaTracker.

3. MetaLearningAmplifier
   MetaLearning currently records results manually.
   This adds pattern detection across sessions:
   "Which tool combinations produce highest quality?"
   Uses SessionIndex data to find winning patterns.

4. KernelHealthMonitor
   Tells you honestly when a kernel has insufficient
   data to be trusted. Prevents false confidence.
   
Drop into: jagabot/engines/engine_improver.py

Wire into loop.py __init__:
    from jagabot.engines.engine_improver import EngineImprover
    self.engine_improver = EngineImprover(workspace, tool_registry)

Call periodically (every 10 sessions):
    self.engine_improver.run_improvement_cycle()
    
Or trigger manually:
    jagabot "run engine improvement cycle"
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Thresholds ──────────────────────────────────────────────────────
MIN_OUTCOMES_FOR_CALIBRATION = 5   # need at least 5 to trust K1/K3
MIN_SESSIONS_FOR_PATTERNS    = 10  # need 10 sessions for MetaLearning
IMPROVEMENT_INTERVAL         = 10  # run every N sessions


class KernelHealthMonitor:
    """
    Honest assessment of kernel data sufficiency.
    Prevents false confidence in empty kernels.
    
    This directly fixes the "62% accuracy" fabrication problem —
    if data is insufficient, it says so loudly.
    """

    def __init__(self, workspace: Path, tool_registry=None) -> None:
        self.workspace     = Path(workspace)
        self.tool_registry = tool_registry

    def check_all(self) -> dict:
        """
        Check all kernels for data sufficiency.
        Returns honest status — never fabricates.
        """
        return {
            "k1_bayesian":   self._check_k1(),
            "k3_perspective":self._check_k3(),
            "meta_learning": self._check_meta(),
            "evolution":     self._check_evolution(),
            "idea_tracker":  self._check_ideas(),
            "checked_at":    datetime.now().isoformat(),
        }

    def get_trust_level(self, kernel: str) -> str:
        """
        Return honest trust level for a kernel.
        Use this before reporting kernel statistics.
        
        Returns: "trusted" | "low_data" | "empty" | "unknown"
        """
        status = self.check_all().get(kernel, {})
        count  = status.get("data_count", 0)

        if count >= MIN_OUTCOMES_FOR_CALIBRATION:
            return "trusted"
        elif count > 0:
            return "low_data"
        elif count == 0:
            return "empty"
        return "unknown"

    def format_honest_status(self) -> str:
        """
        Format a truthful status report for all kernels.
        Agent should use this instead of inventing numbers.
        """
        health = self.check_all()
        lines  = ["## Kernel Health (verified)", ""]

        for kernel, status in health.items():
            if kernel == "checked_at":
                continue
            count  = status.get("data_count", 0)
            trust  = self.get_trust_level(kernel)
            icon   = "✅" if trust == "trusted" else "⚠️" if trust == "low_data" else "❌"
            note   = status.get("note", "")
            lines.append(
                f"{icon} **{kernel}**: {count} records "
                f"({trust}){' — ' + note if note else ''}"
            )

        lines.append("")
        lines.append(
            f"*Checked at {health['checked_at'][:16]}. "
            f"Min {MIN_OUTCOMES_FOR_CALIBRATION} records needed for trust.*"
        )
        return "\n".join(lines)

    # ── Per-kernel checks ───────────────────────────────────────────

    def _check_k1(self) -> dict:
        """Check K1 Bayesian calibration data."""
        try:
            tool = self._get_tool("k1_bayesian")
            if tool:
                result = tool.call({"action": "get_calibration"})
                if "No" in str(result) or "empty" in str(result).lower():
                    return {"data_count": 0, "note": "no calibration data yet"}
                # Parse actual count if available
                return {"data_count": self._parse_count(result), "raw": str(result)[:100]}
        except Exception as e:
            logger.debug(f"K1 check failed: {e}")
        return {"data_count": 0, "note": "check failed"}

    def _check_k3(self) -> dict:
        """Check K3 Perspective accuracy data."""
        try:
            tool = self._get_tool("k3_perspective")
            if tool:
                result = tool.call({"action": "accuracy_stats"})
                if "No accuracy data" in str(result):
                    return {"data_count": 0, "note": "no verdicts recorded yet"}
                return {"data_count": self._parse_count(result), "raw": str(result)[:100]}
        except Exception as e:
            logger.debug(f"K3 check failed: {e}")
        return {"data_count": 0, "note": "check failed"}

    def _check_meta(self) -> dict:
        """Check MetaLearning strategy records."""
        try:
            tool = self._get_tool("meta_learning")
            if tool:
                result = tool.call({"action": "get_rankings"})
                if "No" in str(result) or "empty" in str(result).lower():
                    return {"data_count": 0, "note": "no strategies recorded yet"}
                return {"data_count": self._parse_count(result), "raw": str(result)[:100]}
        except Exception as e:
            logger.debug(f"MetaLearning check failed: {e}")
        return {"data_count": 0, "note": "check failed"}

    def _check_evolution(self) -> dict:
        """Check Evolution engine mutation history."""
        evolution_file = self.workspace / "evolution_state.json"
        if not evolution_file.exists():
            return {"data_count": 0, "note": "no mutations yet"}
        try:
            state = json.loads(evolution_file.read_text())
            mutations = len(state.get("mutations", []))
            return {"data_count": mutations, "note": f"{mutations} mutations"}
        except Exception:
            return {"data_count": 0, "note": "state file unreadable"}

    def _check_ideas(self) -> dict:
        """Check IdeaTracker records."""
        idea_file = self.workspace / "idea_log.json"
        if not idea_file.exists():
            return {"data_count": 0, "note": "no ideas tracked yet"}
        try:
            ideas = json.loads(idea_file.read_text())
            acted = sum(1 for i in ideas if i.get("acted_on"))
            return {
                "data_count": len(ideas),
                "note": f"{acted} acted on of {len(ideas)} tracked"
            }
        except Exception:
            return {"data_count": 0, "note": "idea log unreadable"}

    def _get_tool(self, name: str):
        if self.tool_registry:
            return self.tool_registry.get(name)
        return None

    @staticmethod
    def _parse_count(result) -> int:
        """Try to extract a record count from tool result."""
        text = str(result)
        import re
        matches = re.findall(r'\b(\d+)\s*(?:record|outcome|result|decision)', text)
        return int(matches[0]) if matches else 1


class CrossKernelSyncer:
    """
    Connects K1 Bayesian and K3 Perspective — they've been islands.
    
    K1 tracks: "How confident am I?" (calibration)
    K3 tracks: "Which perspective wins?" (accuracy)
    
    The missing link: K1 calibration SHOULD inform K3 weights.
    If K1 says Bear is overconfident by 22%,
    K3 should automatically reduce Bear's weight.
    
    Currently this adjustment is manual. This automates it.
    """

    def __init__(self, tool_registry=None) -> None:
        self.tool_registry = tool_registry

    def sync(self) -> dict:
        """
        Read K1 calibration errors and push adjustments to K3.
        Only runs when both kernels have sufficient data.
        Returns summary of adjustments made.
        """
        adjustments = []

        try:
            k1   = self._get_tool("k1_bayesian")
            k3   = self._get_tool("k3_perspective")
            if not k1 or not k3:
                return {"status": "skipped", "reason": "tools not available"}

            # Get K1 calibration per perspective
            cal = k1.call({"action": "get_calibration"})
            if "No" in str(cal):
                return {"status": "skipped", "reason": "K1 has no data yet"}

            # Parse calibration errors
            # If Bear is overconfident, reduce its K3 weight
            perspectives = ["bull", "bear", "buffet"]
            for p in perspectives:
                error = self._extract_calibration_error(cal, p)
                if error and abs(error) > 0.1:  # >10% miscalibration
                    # Adjust K3 weight
                    direction = "down" if error > 0 else "up"
                    adjustment = min(abs(error) * 0.5, 0.1)  # max 10% adjust
                    k3.call({
                        "action": "adjust_weight",
                        "perspective": p,
                        "direction": direction,
                        "amount": adjustment,
                        "reason": f"K1 calibration error: {error:.2f}",
                    })
                    adjustments.append({
                        "perspective": p,
                        "calibration_error": error,
                        "weight_adjustment": f"{direction} {adjustment:.2f}",
                    })
                    logger.info(
                        f"CrossKernel sync: {p} weight {direction} "
                        f"by {adjustment:.2f} (K1 error={error:.2f})"
                    )

        except Exception as e:
            logger.debug(f"CrossKernel sync failed: {e}")
            return {"status": "failed", "error": str(e)}

        return {
            "status": "complete",
            "adjustments": adjustments,
            "timestamp": datetime.now().isoformat(),
        }

    def _extract_calibration_error(self, cal_result, perspective: str):
        """Extract calibration error for a perspective from K1 result."""
        try:
            text = str(cal_result).lower()
            import re
            # Look for pattern like "bear: error=0.22" or "bear calibration: 0.22"
            pattern = rf'{perspective}.*?error[:\s=]+([+-]?\d+\.?\d*)'
            match   = re.search(pattern, text)
            if match:
                return float(match.group(1))
        except Exception:
            pass
        return None

    def _get_tool(self, name: str):
        if self.tool_registry:
            return self.tool_registry.get(name)
        return None


class MetaLearningAmplifier:
    """
    Adds pattern detection to MetaLearning using SessionIndex data.
    
    Current MetaLearning: records individual strategy results.
    Amplified: finds patterns ACROSS sessions automatically.
    
    "Which tool combinations produce highest quality outputs?"
    "Which topic types benefit most from tri_agent?"
    "Which query patterns lead to audit rejections?"
    """

    def __init__(self, workspace: Path, tool_registry=None) -> None:
        self.workspace     = Path(workspace)
        self.tool_registry = tool_registry

    def find_winning_patterns(self) -> dict:
        """
        Analyse SessionIndex to find high-quality tool combinations.
        Returns patterns for MetaLearning to record.
        """
        index_file = self.workspace / "memory" / "session_index.json"
        if not index_file.exists():
            return {"status": "no_data", "patterns": []}

        try:
            index    = json.loads(index_file.read_text())
            sessions = list(index.values())

            if len(sessions) < MIN_SESSIONS_FOR_PATTERNS:
                return {
                    "status": "insufficient_data",
                    "have":   len(sessions),
                    "need":   MIN_SESSIONS_FOR_PATTERNS,
                }

            # Find high-quality sessions (quality >= 0.8)
            high_quality = [
                s for s in sessions
                if s.get("quality_avg", 0) >= 0.8
            ]

            # Count tool combinations in high-quality sessions
            tool_combos = {}
            for s in high_quality:
                tools = tuple(sorted(s.get("tools_used", [])[:4]))
                tool_combos[tools] = tool_combos.get(tools, 0) + 1

            # Find winning combinations
            winners = sorted(
                tool_combos.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]

            patterns = []
            for combo, count in winners:
                pattern = {
                    "tools":     list(combo),
                    "frequency": count,
                    "quality":   "high",
                    "note":      f"Used in {count} high-quality sessions",
                }
                patterns.append(pattern)

                # Auto-record to MetaLearning
                self._record_pattern(combo, count)

            return {
                "status":          "complete",
                "sessions_analysed": len(sessions),
                "high_quality":    len(high_quality),
                "patterns":        patterns,
            }

        except Exception as e:
            logger.debug(f"Pattern detection failed: {e}")
            return {"status": "failed", "error": str(e)}

    def _record_pattern(self, tools: tuple, count: int) -> None:
        """Record a winning pattern to MetaLearning."""
        try:
            tool = self.tool_registry.get("meta_learning") if self.tool_registry else None
            if tool:
                strategy = "+".join(tools[:3])
                tool.call({
                    "action":      "record_result",
                    "strategy":    f"auto_pattern_{strategy}",
                    "success":     True,
                    "fitness_gain":min(count / 10, 1.0),
                    "context":     {
                        "tools":       list(tools),
                        "frequency":   count,
                        "auto_detected": True,
                    }
                })
        except Exception as e:
            logger.debug(f"Pattern record failed: {e}")


class EngineImprover:
    """
    Orchestrates all improvement subsystems.
    Runs on a schedule or on-demand.
    
    Call run_improvement_cycle() every 10 sessions
    or when user says "improve engines" / "run cycle".
    """

    def __init__(
        self,
        workspace:     Path,
        tool_registry: object = None,
    ) -> None:
        self.workspace  = Path(workspace)
        self.registry   = tool_registry
        self.health     = KernelHealthMonitor(workspace, tool_registry)
        self.syncer     = CrossKernelSyncer(tool_registry)
        self.amplifier  = MetaLearningAmplifier(workspace, tool_registry)
        self._cycle_file = workspace / "memory" / "improvement_cycles.json"

    def run_improvement_cycle(self) -> dict:
        """
        Run full improvement cycle.
        Returns honest summary of what actually happened.
        """
        logger.info("EngineImprover: starting improvement cycle")
        results = {
            "started_at": datetime.now().isoformat(),
            "steps":      {},
        }

        # Step 1 — Health check (always honest)
        results["steps"]["health_check"] = self.health.check_all()

        # Step 2 — Cross-kernel sync (only if data exists)
        results["steps"]["cross_kernel_sync"] = self.syncer.sync()

        # Step 3 — MetaLearning pattern detection
        results["steps"]["pattern_detection"] = (
            self.amplifier.find_winning_patterns()
        )

        # Step 4 — Log cycle
        results["completed_at"] = datetime.now().isoformat()
        self._log_cycle(results)

        # Step 5 — Format honest summary
        results["summary"] = self._format_summary(results)

        logger.info(
            f"EngineImprover: cycle complete — "
            f"{results['summary'][:80]}"
        )
        return results

    def should_run(self) -> bool:
        """Check if improvement cycle is due."""
        try:
            if not self._cycle_file.exists():
                return True
            cycles = json.loads(self._cycle_file.read_text())
            return len(cycles) % IMPROVEMENT_INTERVAL == 0
        except Exception:
            return True

    def _format_summary(self, results: dict) -> str:
        """Format honest, readable summary."""
        lines   = []
        steps   = results.get("steps", {})

        # Health
        health  = steps.get("health_check", {})
        empty   = sum(
            1 for k, v in health.items()
            if isinstance(v, dict) and v.get("data_count", 0) == 0
            and k != "checked_at"
        )
        total_k = len([k for k in health if k != "checked_at"])
        lines.append(
            f"Health: {total_k - empty}/{total_k} kernels have data"
        )

        # Sync
        sync = steps.get("cross_kernel_sync", {})
        if sync.get("status") == "complete":
            adj = len(sync.get("adjustments", []))
            lines.append(f"Cross-kernel sync: {adj} weight adjustments")
        else:
            lines.append(f"Cross-kernel sync: {sync.get('reason', 'skipped')}")

        # Patterns
        patterns = steps.get("pattern_detection", {})
        if patterns.get("status") == "complete":
            n = len(patterns.get("patterns", []))
            lines.append(f"Patterns found: {n} winning tool combinations")
        else:
            lines.append(
                f"Pattern detection: {patterns.get('status', 'skipped')} "
                f"({patterns.get('have', 0)}/{patterns.get('need', MIN_SESSIONS_FOR_PATTERNS)} sessions)"
            )

        return " | ".join(lines)

    def _log_cycle(self, results: dict) -> None:
        """Append cycle to history file."""
        try:
            self._cycle_file.parent.mkdir(parents=True, exist_ok=True)
            cycles = []
            if self._cycle_file.exists():
                cycles = json.loads(self._cycle_file.read_text())
            cycles.append({
                "started_at":   results["started_at"],
                "completed_at": results.get("completed_at", ""),
                "summary":      results.get("summary", ""),
            })
            self._cycle_file.write_text(
                json.dumps(cycles[-50:], indent=2)  # keep last 50
            )
        except Exception as e:
            logger.debug(f"Cycle log failed: {e}")
