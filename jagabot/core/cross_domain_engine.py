"""
Cross-Domain Insight Engine — Module 4

Detects analogies between patterns across different domains.
Finds when a pattern in domain A structurally resembles a pattern
in domain B, generating cross-domain insights.

Example insights:
  - "GDP declining follows same lagged pattern as field maturation"
  - "Market consolidation mirrors research citation decline"
  - "Volatility clustering appears in both finance and epidemic spread"

Data sources:
  - HypothesisEngine (stored hypotheses across domains)
  - MemoryManager (facts extracted from conversations)
  - BrierScorer (trust scores per domain)
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


# ── Pattern abstractions ──────────────────────────────────────────

PATTERN_SIGNATURES = {
    # Economic patterns
    "lagged_effect":     ["then", "follows", "after", "lag", "delay", "eventual"],
    "threshold_breach":  ["exceeds", "breach", "above", "below", "threshold", "limit"],
    "mean_reversion":    ["return", "revert", "normalize", "average", "stable"],
    "momentum":          ["continue", "persist", "remain", "sustained", "elevated"],
    "consolidation":     ["mature", "established", "build on", "incremental", "entrant"],
    "acceleration":      ["rapid", "breakthrough", "surge", "spike", "explosive"],
    "decay":             ["decline", "decrease", "reduce", "fall", "contract"],
    "growth":            ["increase", "grow", "rise", "expand", "improve"],
}

DOMAIN_CONTEXTS = {
    "financial":   ["market", "price", "investment", "GDP", "inflation", "risk"],
    "research":    ["citation", "paper", "field", "breakthrough", "entrant", "study"],
    "engineering": ["system", "code", "tool", "failure", "performance", "scale"],
    "calibration": ["confidence", "accuracy", "brier", "forecast", "prediction"],
    "general":     ["pattern", "trend", "behavior", "outcome", "result"],
}


# ── Data classes ──────────────────────────────────────────────────

@dataclass
class DomainPattern:
    """An abstracted pattern from one domain."""
    domain:     str
    pattern_type: str    # from PATTERN_SIGNATURES keys
    condition:  str      # original condition text
    prediction: str      # original prediction text
    confidence: float
    source_id:  str      # hypothesis ID or memory entry ID


@dataclass
class CrossDomainInsight:
    """An insight connecting patterns across two domains."""
    id:           str
    domain_a:     str
    domain_b:     str
    pattern_type: str    # shared pattern type
    condition_a:  str
    condition_b:  str
    analogy:      str    # human-readable insight statement
    strength:     float  # 0-1 how strong the analogy is
    confidence:   float  # combined confidence
    created_at:   str = field(default_factory=lambda: datetime.now().isoformat())
    validated:    bool = False
    notes:        str = ""


# ── Pattern extractor ─────────────────────────────────────────────

def extract_pattern_type(text: str) -> str:
    """Extract abstract pattern type from text."""
    text_lower = text.lower()
    best_match = "momentum"  # default
    best_score = 0

    for pattern, keywords in PATTERN_SIGNATURES.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_match = pattern

    return best_match


def compute_analogy_strength(pattern_a: DomainPattern, pattern_b: DomainPattern) -> float:
    """Compute how strong the analogy between two patterns is."""
    if pattern_a.pattern_type != pattern_b.pattern_type:
        return 0.0

    # Same pattern type = base strength
    strength = 0.5

    # Boost if confidence levels are similar
    conf_diff = abs(pattern_a.confidence - pattern_b.confidence)
    if conf_diff < 0.1:
        strength += 0.2
    elif conf_diff < 0.2:
        strength += 0.1

    # Boost if domains are genuinely different (not general)
    if (pattern_a.domain != "general" and
        pattern_b.domain != "general" and
        pattern_a.domain != pattern_b.domain):
        strength += 0.3

    return min(1.0, strength)


def generate_analogy_statement(
    pattern_a: DomainPattern,
    pattern_b: DomainPattern,
    strength:  float,
) -> str:
    """Generate human-readable analogy insight."""
    strength_label = (
        "strong structural analogy" if strength >= 0.8
        else "moderate analogy" if strength >= 0.6
        else "weak analogy"
    )

    return (
        f"[{strength_label.upper()}] "
        f"The {pattern_a.pattern_type} pattern in {pattern_a.domain} "
        f"('IF {pattern_a.condition[:60]}...') "
        f"mirrors the same pattern in {pattern_b.domain} "
        f"('IF {pattern_b.condition[:60]}...'). "
        f"Both predict {pattern_a.pattern_type}-type outcomes. "
        f"Cross-domain transfer: insights from {pattern_b.domain} "
        f"may improve {pattern_a.domain} predictions."
    )


# ── Main engine ───────────────────────────────────────────────────

class CrossDomainEngine:
    """
    Detects and stores cross-domain pattern analogies.

    Flow:
        1. load_patterns() — load from hypothesis DB + memory
        2. find_analogies() — detect shared pattern types
        3. generate_insights() — create insight statements
        4. store_insights() — save to insights DB
        5. format_report() — human-readable output
    """

    def __init__(self, workspace: Path, brier_scorer=None):
        self.workspace   = Path(workspace)
        self.brier       = brier_scorer
        self.hyp_db      = self.workspace / "memory" / "hypotheses.db"
        self.db_path     = self.workspace / "memory" / "cross_domain_insights.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS insights (
                id           TEXT PRIMARY KEY,
                domain_a     TEXT,
                domain_b     TEXT,
                pattern_type TEXT,
                condition_a  TEXT,
                condition_b  TEXT,
                analogy      TEXT,
                strength     REAL,
                confidence   REAL,
                validated    INTEGER DEFAULT 0,
                notes        TEXT,
                created_at   TEXT
            )
        """)
        conn.commit()
        conn.close()

    def load_patterns_from_hypotheses(self) -> list[DomainPattern]:
        """Load patterns from stored hypotheses."""
        if not self.hyp_db.exists():
            return []

        try:
            conn = sqlite3.connect(self.hyp_db)
            rows = conn.execute("""
                SELECT id, domain, condition, prediction, confidence
                FROM hypotheses
                WHERE condition IS NOT NULL
            """).fetchall()
            conn.close()
        except Exception as e:
            logger.debug(f"Could not load hypotheses: {e}")
            return []

        patterns = []
        for hid, domain, condition, prediction, confidence in rows:
            pattern_type = extract_pattern_type(f"{condition} {prediction}")
            patterns.append(DomainPattern(
                domain       = domain,
                pattern_type = pattern_type,
                condition    = condition or "",
                prediction   = prediction or "",
                confidence   = confidence or 0.5,
                source_id    = f"hyp:{hid}",
            ))
        return patterns

    def load_patterns_from_memory(self, memory_manager=None) -> list[DomainPattern]:
        """Load patterns from memory manager facts."""
        if not memory_manager:
            return []

        patterns = []
        try:
            entries = memory_manager.search("pattern trend finding conclusion", k=20)
            for entry in entries:
                pattern_type = extract_pattern_type(entry.content)
                domain = entry.topic if hasattr(entry, 'topic') else "general"
                patterns.append(DomainPattern(
                    domain       = domain,
                    pattern_type = pattern_type,
                    condition    = entry.content[:100],
                    prediction   = entry.content[100:200],
                    confidence   = 0.6,
                    source_id    = f"mem:{entry.source}",
                ))
        except Exception as e:
            logger.debug(f"Memory pattern load failed: {e}")

        return patterns

    def find_analogies(
        self,
        patterns: list[DomainPattern],
    ) -> list[CrossDomainInsight]:
        """Find cross-domain analogies between patterns."""
        import uuid
        insights = []
        seen_pairs = set()

        for i, pa in enumerate(patterns):
            for j, pb in enumerate(patterns):
                if i >= j:
                    continue
                if pa.domain == pb.domain:
                    continue  # Skip same-domain pairs

                pair_key = tuple(sorted([pa.source_id, pb.source_id]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                strength = compute_analogy_strength(pa, pb)
                if strength < 0.5:
                    continue  # Only keep meaningful analogies

                analogy = generate_analogy_statement(pa, pb, strength)
                avg_confidence = (pa.confidence + pb.confidence) / 2

                insight = CrossDomainInsight(
                    id           = str(uuid.uuid4())[:8],
                    domain_a     = pa.domain,
                    domain_b     = pb.domain,
                    pattern_type = pa.pattern_type,
                    condition_a  = pa.condition,
                    condition_b  = pb.condition,
                    analogy      = analogy,
                    strength     = strength,
                    confidence   = avg_confidence,
                )
                insights.append(insight)
                logger.info(
                    f"Cross-domain insight [{insight.id}]: "
                    f"{pa.domain} ↔ {pb.domain} "
                    f"({pa.pattern_type}, strength={strength:.2f})"
                )

        return sorted(insights, key=lambda x: x.strength, reverse=True)

    def store_insights(self, insights: list[CrossDomainInsight]) -> None:
        """Save insights to database."""
        conn = sqlite3.connect(self.db_path)
        for ins in insights:
            conn.execute("""
                INSERT OR REPLACE INTO insights
                (id, domain_a, domain_b, pattern_type,
                 condition_a, condition_b, analogy,
                 strength, confidence, validated, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ins.id, ins.domain_a, ins.domain_b, ins.pattern_type,
                ins.condition_a, ins.condition_b, ins.analogy,
                ins.strength, ins.confidence,
                int(ins.validated), ins.notes, ins.created_at,
            ))
        conn.commit()
        conn.close()
        logger.info(f"Stored {len(insights)} cross-domain insights")

    def run(self, memory_manager=None) -> list[CrossDomainInsight]:
        """Full pipeline: load → find → store → return insights."""
        patterns = self.load_patterns_from_hypotheses()
        patterns += self.load_patterns_from_memory(memory_manager)

        logger.info(f"CrossDomainEngine: loaded {len(patterns)} patterns")

        if len(patterns) < 2:
            logger.info("CrossDomainEngine: need at least 2 patterns from different domains")
            return []

        insights = self.find_analogies(patterns)
        if insights:
            self.store_insights(insights)

        return insights

    def format_report(self, insights: list[CrossDomainInsight]) -> str:
        """Format insights as human-readable report."""
        if not insights:
            return (
                "## 🔗 Cross-Domain Insight Engine\n\n"
                "No cross-domain analogies detected yet.\n"
                "Generate more hypotheses across different domains to enable insight detection.\n"
            )

        lines = [
            "## 🔗 Cross-Domain Insights\n",
            f"Found {len(insights)} cross-domain analogy/analogies:\n",
        ]
        for ins in insights:
            strength_emoji = "🔴" if ins.strength >= 0.8 else "🟡" if ins.strength >= 0.6 else "🟢"
            lines.append(f"{strength_emoji} **[{ins.id}]** {ins.domain_a.upper()} ↔ {ins.domain_b.upper()}")
            lines.append(f"   Pattern: `{ins.pattern_type}`")
            lines.append(f"   {ins.analogy}")
            lines.append(f"   Strength: {ins.strength:.0%} | Confidence: {ins.confidence:.0%}")
            lines.append("")

        lines.append("---")
        lines.append("💡 Use these insights to improve predictions in one domain")
        lines.append("   by applying knowledge from the analogous domain.")
        return "\n".join(lines)

    def get_stats(self) -> dict:
        """Return insight statistics."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT domain_a, domain_b, pattern_type,
                   COUNT(*) as count,
                   AVG(strength) as avg_strength,
                   AVG(confidence) as avg_confidence
            FROM insights
            GROUP BY domain_a, domain_b, pattern_type
        """).fetchall()
        conn.close()

        return {
            f"{r[0]}↔{r[1]}": {
                "pattern":    r[2],
                "count":      r[3],
                "avg_strength": round(r[4], 2),
                "avg_confidence": round(r[5], 2),
            }
            for r in rows
        }
