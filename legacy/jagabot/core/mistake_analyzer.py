"""
MistakePatternAnalyzer — Empirical Feedback Loop Phase 2

Learns from wrong outcomes to prevent recurring mistakes.

Flow:
  Outcome marked "wrong" by user
  → MistakeAnalyzer extracts mistake pattern
  → Stores in mistake registry
  → Injects relevant warnings before similar queries
  → BeliefEngine adjusts confidence for affected domains

Patterns detected:
  - Topic patterns: "financial predictions often wrong"
  - Tool patterns: "web search returns stale data"  
  - Confidence patterns: "overconfident when using single source"
  - Domain patterns: "weak in healthcare, strong in engineering"
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from loguru import logger


@dataclass
class MistakePattern:
    """A detected mistake pattern."""
    id:           str
    pattern_type: str    # "topic" | "tool" | "confidence" | "domain"
    description:  str    # human readable
    domain:       str
    frequency:    int    # how many times seen
    last_seen:    str
    example:      str    # example conclusion that was wrong
    prevention:   str    # suggested prevention


class MistakePatternAnalyzer:
    """
    Analyzes wrong outcomes to detect recurring mistake patterns.
    Injects warnings before similar queries.
    """

    def __init__(self, workspace: Path):
        self.workspace     = Path(workspace)
        self.outcomes_path = self.workspace / "pending_outcomes.json"
        self.db_path       = self.workspace / "memory" / "mistakes.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._pattern_cache: list[MistakePattern] = []

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mistakes (
                id           TEXT PRIMARY KEY,
                pattern_type TEXT,
                description  TEXT,
                domain       TEXT,
                frequency    INTEGER DEFAULT 1,
                last_seen    TEXT,
                example      TEXT,
                prevention   TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wrong_outcomes (
                id           TEXT PRIMARY KEY,
                conclusion   TEXT,
                domain       TEXT,
                confidence   REAL,
                recorded_at  TEXT,
                pattern_ids  TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _detect_domain(self, text: str) -> str:
        """Detect domain from conclusion text."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["stock", "price", "market", "financial", "invest"]):
            return "financial"
        elif any(w in text_lower for w in ["research", "hypothesis", "study", "paper"]):
            return "research"
        elif any(w in text_lower for w in ["code", "tool", "api", "python", "function"]):
            return "engineering"
        elif any(w in text_lower for w in ["subagent", "spawn", "parallel", "agent"]):
            return "multi_agent"
        return "general"

    def _detect_patterns(self, conclusion: str, confidence: float, domain: str) -> list[str]:
        """Detect which mistake patterns apply to this wrong outcome."""
        patterns = []

        # High confidence wrong → overconfidence pattern
        if confidence >= 0.8:
            patterns.append("overconfidence")

        # Financial predictions
        if domain == "financial" and any(
            w in conclusion.lower() for w in ["will", "expect", "predict", "likely"]
        ):
            patterns.append("financial_prediction")

        # Single source overreliance
        if any(w in conclusion.lower() for w in ["web scraping", "duckduckgo", "search"]):
            patterns.append("unverified_source")

        # Tool assumption
        if any(w in conclusion.lower() for w in ["tool", "function", "api", "return"]):
            patterns.append("tool_assumption")

        return patterns if patterns else ["general_error"]

    def _get_prevention(self, pattern: str) -> str:
        """Get prevention advice for a pattern."""
        prevention_map = {
            "overconfidence":        "Lower confidence when using single source. Apply Rule 6 calibration matrix.",
            "financial_prediction":  "Financial predictions require 2+ verified sources. Max confidence 60% for web scraping.",
            "unverified_source":     "DuckDuckGo scraping = degraded quality. Cross-verify with Yahoo Finance API.",
            "tool_assumption":       "Verify tool signatures before use. Check documentation matches implementation.",
            "general_error":         "Apply assumption audit (Rule 4) before concluding. List hidden assumptions.",
        }
        return prevention_map.get(pattern, "Apply adversarial guardrails before concluding.")

    def record_wrong_outcome(self, outcome: dict) -> list[str]:
        """
        Record a wrong outcome and extract patterns.
        Returns list of pattern IDs detected.
        """
        conclusion = outcome.get("conclusion", "")
        confidence = float(outcome.get("confidence", 0.5))
        domain     = self._detect_domain(conclusion)
        patterns   = self._detect_patterns(conclusion, confidence, domain)
        pattern_ids = []

        conn = sqlite3.connect(self.db_path)
        for pattern in patterns:
            pat_id = f"{domain}:{pattern}"
            pattern_ids.append(pat_id)

            # Check if pattern exists
            existing = conn.execute(
                "SELECT frequency FROM mistakes WHERE id=?", (pat_id,)
            ).fetchone()

            if existing:
                conn.execute("""
                    UPDATE mistakes SET
                        frequency = frequency + 1,
                        last_seen = ?,
                        example   = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), conclusion[:200], pat_id))
                logger.info(f"MistakeAnalyzer: pattern '{pat_id}' frequency +1")
            else:
                prevention = self._get_prevention(pattern)
                conn.execute("""
                    INSERT INTO mistakes
                    (id, pattern_type, description, domain, frequency, last_seen, example, prevention)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                """, (
                    pat_id, pattern,
                    f"{pattern.replace('_', ' ').title()} in {domain} domain",
                    domain, datetime.now().isoformat(),
                    conclusion[:200], prevention
                ))
                logger.info(f"MistakeAnalyzer: new pattern '{pat_id}' detected")

        # Record wrong outcome
        conn.execute("""
            INSERT OR REPLACE INTO wrong_outcomes
            (id, conclusion, domain, confidence, recorded_at, pattern_ids)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            outcome.get("id", "unknown"),
            conclusion[:200], domain, confidence,
            datetime.now().isoformat(),
            json.dumps(pattern_ids)
        ))
        conn.commit()
        conn.close()
        return pattern_ids

    def get_warnings_for_query(self, query: str) -> list[str]:
        """
        Get relevant warnings for a query based on past mistakes.
        Called before each LLM response to inject relevant warnings.
        """
        domain = self._detect_domain(query)
        conn   = sqlite3.connect(self.db_path)

        # Get patterns for this domain with frequency >= 2
        rows = conn.execute("""
            SELECT id, description, prevention, frequency
            FROM mistakes
            WHERE (domain = ? OR domain = 'general')
            AND frequency >= 2
            ORDER BY frequency DESC
            LIMIT 3
        """, (domain,)).fetchall()
        conn.close()

        warnings = []
        for pat_id, desc, prevention, freq in rows:
            warnings.append(
                f"⚠️ Known pattern ({freq}x): {desc} → {prevention}"
            )
        return warnings

    def process_new_wrong_outcomes(self) -> int:
        """Process any new wrong outcomes from pending_outcomes.json."""
        if not self.outcomes_path.exists():
            return 0

        try:
            data    = json.loads(self.outcomes_path.read_text())
            wrong   = [o for o in data if o.get("verified") and o.get("outcome") == "wrong"]
        except Exception:
            return 0

        # Check which are already recorded
        conn = sqlite3.connect(self.db_path)
        recorded = {r[0] for r in conn.execute("SELECT id FROM wrong_outcomes").fetchall()}
        conn.close()

        new_wrong = [o for o in wrong if o.get("id") not in recorded]
        for outcome in new_wrong:
            self.record_wrong_outcome(outcome)

        if new_wrong:
            logger.info(f"MistakeAnalyzer: processed {len(new_wrong)} new wrong outcomes")

        return len(new_wrong)

    def get_stats(self) -> dict:
        """Return mistake pattern statistics."""
        conn = sqlite3.connect(self.db_path)
        patterns = conn.execute("""
            SELECT id, frequency, domain FROM mistakes
            ORDER BY frequency DESC
        """).fetchall()
        total_wrong = conn.execute("SELECT COUNT(*) FROM wrong_outcomes").fetchone()[0]
        conn.close()

        return {
            "total_wrong":     total_wrong,
            "patterns":        [{"id": r[0], "freq": r[1], "domain": r[2]} for r in patterns],
            "pattern_count":   len(patterns),
        }
