# jagabot/agent/memory_outcome_bridge.py
"""
MemoryOutcomeBridge — Connects OutcomeTracker to MemoryFleet.

The missing link between:
    OutcomeTracker  → knows if conclusions were right/wrong
    MemoryFleet     → stores findings in fractal nodes
    MEMORY.md       → curated long-term knowledge base

Without this bridge:
    MEMORY.md accumulates content but never learns
    Fractal nodes store claims with no verification status
    Wrong conclusions stay in memory forever

With this bridge:
    Every verified outcome updates its fractal node
    MEMORY.md entries are tagged [VERIFIED ✅] or [WRONG ❌]
    Memory workers see verification status when summarizing
    Wrong conclusions get flagged, not silently repeated

Wire into loop.py __init__:
    from jagabot.agent.memory_outcome_bridge import MemoryOutcomeBridge
    self.mem_bridge = MemoryOutcomeBridge(workspace, tool_registry)

Wire into outcome_tracker.py after recording outcome:
    self.bridge.on_outcome_verified(
        conclusion=conclusion,
        result="correct" | "wrong" | "partial",
        session_key=session_key,
        topic_tag=topic_tag,
    )
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Verification markers written to MEMORY.md ──────────────────────
MARKERS = {
    "correct": "✅ VERIFIED CORRECT",
    "wrong":   "❌ VERIFIED WRONG — do not repeat",
    "partial": "⚠️ PARTIALLY CORRECT",
    "pending": "🔲 UNVERIFIED",
}

# Confidence boost/penalty when updating fractal nodes
CONFIDENCE_DELTA = {
    "correct": +0.20,
    "wrong":   -0.40,   # penalise wrong harder than reward correct
    "partial": +0.05,
}


class MemoryOutcomeBridge:
    """
    Keeps memory honest by tagging verified conclusions.

    Three jobs:
    1. TAG    — mark MEMORY.md entries with verification status
    2. UPDATE — strengthen/weaken fractal nodes based on outcomes
    3. PRUNE  — flag wrong conclusions for removal from active memory
    """

    def __init__(
        self,
        workspace:     Path,
        tool_registry: object = None,
    ) -> None:
        self.workspace     = Path(workspace)
        self.memory_dir    = self.workspace / "memory"
        self.tool_registry = tool_registry
        self.memory_file   = self.memory_dir / "MEMORY.md"
        self.history_file  = self.memory_dir / "HISTORY.md"
        self.bridge_log    = self.memory_dir / "bridge_log.json"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_bridge_log()

    # ── Public API ──────────────────────────────────────────────────

    def on_outcome_verified(
        self,
        conclusion:  str,
        result:      str,       # "correct" | "wrong" | "partial"
        session_key: str = "",
        topic_tag:   str = "",
        evidence:    str = "",
    ) -> dict:
        """
        Called when OutcomeTracker verifies a conclusion.
        Updates MEMORY.md, fractal nodes, and bridge log.
        Returns summary of what was updated.
        """
        updates = {
            "conclusion":     conclusion[:80],
            "result":         result,
            "memory_updated": False,
            "fractal_updated":False,
            "history_logged": False,
            "timestamp":      datetime.now().isoformat(),
        }

        # 1. Tag MEMORY.md entry
        if self._tag_memory_entry(conclusion, result):
            updates["memory_updated"] = True
            logger.info(
                f"Bridge: tagged MEMORY.md — "
                f"'{conclusion[:40]}' → {result}"
            )

        # 2. Update fractal node confidence
        if self._update_fractal_node(conclusion, result, topic_tag):
            updates["fractal_updated"] = True
            logger.info(
                f"Bridge: updated fractal node — "
                f"confidence delta {CONFIDENCE_DELTA.get(result, 0):+.2f}"
            )

        # 3. If wrong — append warning to MEMORY.md
        if result == "wrong":
            self._append_correction(conclusion, evidence)
            logger.warning(
                f"Bridge: conclusion marked WRONG — "
                f"'{conclusion[:60]}'"
            )

        # 4. Log to HISTORY.md
        self._log_to_history(conclusion, result, session_key, evidence)
        updates["history_logged"] = True

        # 5. Save to bridge log
        self._save_bridge_log(updates)

        return updates

    def get_verification_summary(self) -> dict:
        """
        Return honest summary of memory verification status.
        Use this instead of fabricating memory statistics.
        """
        log    = self._load_bridge_log()
        total  = len(log)

        if total == 0:
            return {
                "status":  "empty",
                "message": "No outcomes verified yet. "
                           "Memory has not been quality-checked.",
                "total":   0,
            }

        correct = sum(1 for e in log if e.get("result") == "correct")
        wrong   = sum(1 for e in log if e.get("result") == "wrong")
        partial = sum(1 for e in log if e.get("result") == "partial")

        return {
            "status":        "active",
            "total":         total,
            "correct":       correct,
            "wrong":         wrong,
            "partial":       partial,
            "accuracy":      round(correct / total, 2) if total else 0,
            "memory_health": self._assess_memory_health(correct, wrong, total),
        }

    def get_wrong_conclusions(self) -> list[str]:
        """
        Return list of conclusions verified as WRONG.
        Agent should avoid repeating these.
        """
        log = self._load_bridge_log()
        return [
            e["conclusion"] for e in log
            if e.get("result") == "wrong"
        ]

    def inject_wrong_conclusions_guard(self) -> str:
        """
        Returns context snippet warning agent about wrong conclusions.
        Inject this into Layer 1 context to prevent repetition.
        """
        wrong = self.get_wrong_conclusions()
        if not wrong:
            return ""

        lines = [
            "## ⚠️ Previously Verified as WRONG — Do Not Repeat",
            "",
        ]
        for w in wrong[:5]:  # max 5 in context
            lines.append(f"- ~~{w[:80]}~~")
        lines.append("")

        return "\n".join(lines)

    # ── MEMORY.md operations ────────────────────────────────────────

    def _tag_memory_entry(self, conclusion: str, result: str) -> bool:
        """
        Find conclusion in MEMORY.md and add verification tag.
        Uses fuzzy matching — conclusion may be paraphrased.
        """
        if not self.memory_file.exists():
            return False

        try:
            content = self.memory_file.read_text(encoding="utf-8")
            marker  = MARKERS.get(result, "")

            # Find best matching line
            best_line, best_score = self._fuzzy_find(
                conclusion, content
            )

            if best_line and best_score > 0.5:
                # Already tagged?
                if any(m in best_line for m in MARKERS.values()):
                    # Update existing tag
                    for old_marker in MARKERS.values():
                        best_line = best_line.replace(
                            f" [{old_marker}]", ""
                        )
                tagged_line = f"{best_line.rstrip()} [{marker}]"
                content     = content.replace(best_line, tagged_line)
                self.memory_file.write_text(content, encoding="utf-8")
                return True

            # Not found — append as new verified entry
            self._append_verified_entry(conclusion, result)
            return True

        except Exception as e:
            logger.debug(f"Memory tag failed: {e}")
            return False

    def _append_correction(self, conclusion: str, evidence: str) -> None:
        """Append a correction notice to MEMORY.md."""
        try:
            correction = (
                f"\n## ❌ CORRECTION ({datetime.now().strftime('%Y-%m-%d')})\n\n"
                f"**Wrong conclusion:** {conclusion}\n\n"
                f"**Evidence:** {evidence if evidence else 'User verified as incorrect'}\n\n"
                f"**Action:** Do not repeat this conclusion. "
                f"Re-research with updated assumptions.\n"
            )
            with open(self.memory_file, "a", encoding="utf-8") as f:
                f.write(correction)
        except Exception as e:
            logger.debug(f"Correction append failed: {e}")

    def _append_verified_entry(
        self, conclusion: str, result: str
    ) -> None:
        """Append a new verified entry to MEMORY.md."""
        try:
            marker  = MARKERS.get(result, "")
            ts      = datetime.now().strftime("%Y-%m-%d")
            entry   = (
                f"\n## [{marker}] ({ts})\n\n"
                f"{conclusion}\n"
            )
            with open(self.memory_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            logger.debug(f"Entry append failed: {e}")

    # ── Fractal node operations ─────────────────────────────────────

    def _update_fractal_node(
        self,
        conclusion: str,
        result:     str,
        topic_tag:  str,
    ) -> bool:
        """
        Update fractal node confidence based on outcome.
        Strengthens correct conclusions, weakens wrong ones.
        """
        try:
            tool = self._get_tool("memory_fleet")
            if not tool:
                return False

            delta = CONFIDENCE_DELTA.get(result, 0)

            # Tools have async execute(), not call()
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(tool.execute(
                    action="update_node_confidence",
                    topic=topic_tag,
                    conclusion=conclusion[:100],
                    delta=delta,
                    verified=result != "pending",
                    result=result,
                    timestamp=datetime.now().isoformat(),
                ))
            finally:
                loop.close()
            return True

        except Exception as e:
            logger.debug(f"Fractal update failed: {e}")
            return False

    # ── HISTORY.md logging ──────────────────────────────────────────

    def _log_to_history(
        self,
        conclusion:  str,
        result:      str,
        session_key: str,
        evidence:    str,
    ) -> None:
        """Append verification event to HISTORY.md."""
        try:
            marker = MARKERS.get(result, result.upper())
            ts     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            entry  = (
                f"\n[{ts}] OUTCOME_VERIFIED | {marker} | "
                f"session={session_key}\n"
                f"  conclusion: {conclusion[:100]}\n"
            )
            if evidence:
                entry += f"  evidence: {evidence[:100]}\n"

            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            logger.debug(f"History log failed: {e}")

    # ── Helpers ─────────────────────────────────────────────────────

    def _fuzzy_find(
        self, needle: str, haystack: str
    ) -> tuple[str, float]:
        """
        Find the line in haystack most similar to needle.
        Returns (line, score) where score is 0.0-1.0.
        Simple word-overlap — no external dependencies.
        """
        needle_words = set(needle.lower().split())
        best_line    = ""
        best_score   = 0.0

        for line in haystack.split("\n"):
            if len(line.strip()) < 10:
                continue
            line_words = set(line.lower().split())
            if not needle_words or not line_words:
                continue
            overlap = len(needle_words & line_words)
            score   = overlap / max(len(needle_words), len(line_words))
            if score > best_score:
                best_score = score
                best_line  = line

        return best_line, best_score

    def _assess_memory_health(
        self, correct: int, wrong: int, total: int
    ) -> str:
        if total < 5:
            return "insufficient_data"
        accuracy = correct / total
        if accuracy >= 0.8:
            return "healthy"
        elif accuracy >= 0.6:
            return "moderate"
        else:
            return "needs_review"

    def _get_tool(self, name: str):
        if self.tool_registry:
            return self.tool_registry.get(name)
        return None

    def _ensure_bridge_log(self) -> None:
        if not self.bridge_log.exists():
            self.bridge_log.write_text("[]", encoding="utf-8")

    def _load_bridge_log(self) -> list:
        try:
            return json.loads(
                self.bridge_log.read_text(encoding="utf-8")
            )
        except Exception:
            return []

    def _save_bridge_log(self, entry: dict) -> None:
        try:
            log = self._load_bridge_log()
            log.append(entry)
            self.bridge_log.write_text(
                json.dumps(log[-200:], indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.debug(f"Bridge log save failed: {e}")
