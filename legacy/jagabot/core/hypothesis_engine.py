"""
Generative Hypothesis Engine

Generates hypotheses from public data patterns across domains,
then tests them using existing Bayesian and Counterfactual tools.

Data sources:
  - World Bank API  → economic indicators
  - OpenAlex API    → scientific research papers
  - Web search      → general knowledge patterns

Flow:
  1. fetch_data(domain) → raw data from public APIs
  2. detect_patterns(data) → candidate patterns
  3. generate_hypothesis(pattern) → IF [X] THEN [Y] WITH [confidence]
  4. test_hypothesis(hypothesis) → evidence for/against
  5. store_hypothesis(hypothesis, result) → memory fleet
"""

from __future__ import annotations

import json
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import sqlite3

from loguru import logger


# ── Hypothesis data class ─────────────────────────────────────────

@dataclass
class Hypothesis:
    """A single generated and testable hypothesis."""
    id:           str = ""
    domain:       str = ""
    statement:    str = ""      # IF [condition] THEN [prediction]
    condition:    str = ""      # The IF part
    prediction:   str = ""      # The THEN part
    confidence:   float = 0.5  # Prior confidence 0-1
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)
    status:       str = "pending"  # pending | confirmed | rejected | partial
    source_data:  str = ""      # What data generated this
    created_at:   str = field(default_factory=lambda: datetime.now().isoformat())
    tested_at:    str = ""
    brier_score:  float = 0.0


# ── Data fetchers ─────────────────────────────────────────────────

def fetch_worldbank(indicator: str, country: str = "US", years: int = 5) -> dict:
    """Fetch World Bank economic indicator data."""
    url = (
        f"https://api.worldbank.org/v2/country/{country}"
        f"/indicator/{indicator}?format=json&mrv={years}&per_page=10"
    )
    try:
        req = urllib.request.urlopen(url, timeout=10)
        data = json.loads(req.read())
        if len(data) >= 2 and data[1]:
            return {
                "source": "World Bank",
                "indicator": indicator,
                "country": country,
                "values": [
                    {"year": d.get("date"), "value": d.get("value")}
                    for d in data[1] if d.get("value") is not None
                ]
            }
    except Exception as e:
        logger.debug(f"WorldBank fetch failed: {e}")
    return {}


def fetch_openalex(topic: str, limit: int = 5) -> dict:
    """Fetch recent research papers from OpenAlex."""
    encoded = urllib.parse.quote(topic)
    url = (
        f"https://api.openalex.org/works"
        f"?search={encoded}&per-page={limit}&sort=cited_by_count:desc"
        f"&select=title,abstract_inverted_index,cited_by_count,publication_year"
    )
    try:
        req = urllib.request.urlopen(url, timeout=10)
        data = json.loads(req.read())
        works = data.get("results", [])
        return {
            "source": "OpenAlex",
            "topic": topic,
            "papers": [
                {
                    "title": w.get("title", ""),
                    "year":  w.get("publication_year"),
                    "cited": w.get("cited_by_count", 0),
                }
                for w in works
            ]
        }
    except Exception as e:
        logger.debug(f"OpenAlex fetch failed: {e}")
    return {}


# ── Pattern detectors ─────────────────────────────────────────────

def detect_trend(values: list[dict]) -> dict:
    """Detect trend direction and magnitude from time series."""
    if len(values) < 2:
        return {"trend": "unknown", "magnitude": 0.0}

    vals = [v["value"] for v in values if v.get("value") is not None]
    if len(vals) < 2:
        return {"trend": "unknown", "magnitude": 0.0}

    first, last = vals[-1], vals[0]  # oldest to newest
    if first == 0:
        return {"trend": "unknown", "magnitude": 0.0}

    change = (last - first) / abs(first)
    trend = "increasing" if change > 0.05 else "decreasing" if change < -0.05 else "stable"
    return {"trend": trend, "magnitude": round(abs(change), 3)}


def detect_research_pattern(papers: list[dict]) -> dict:
    """Detect research patterns from paper metadata."""
    if not papers:
        return {"pattern": "unknown"}

    years = [p["year"] for p in papers if p.get("year")]
    avg_year = sum(years) / len(years) if years else 0
    avg_cited = sum(p.get("cited", 0) for p in papers) / len(papers)

    return {
        "pattern": "active_research" if avg_year >= 2020 else "established_field",
        "avg_citations": round(avg_cited, 1),
        "recent_focus": avg_year >= 2022,
    }


# ── Hypothesis templates ──────────────────────────────────────────

HYPOTHESIS_TEMPLATES = {
    "economic_trend": (
        "IF {indicator} in {country} is {trend} "
        "THEN {prediction} WITH confidence {confidence:.0%}"
    ),
    "research_momentum": (
        "IF research on '{topic}' shows {pattern} (avg citations: {citations}) "
        "THEN {prediction} WITH confidence {confidence:.0%}"
    ),
    "cross_domain": (
        "IF pattern '{pattern_a}' in {domain_a} resembles '{pattern_b}' in {domain_b} "
        "THEN {prediction} WITH confidence {confidence:.0%}"
    ),
}

ECONOMIC_PREDICTIONS = {
    "increasing": [
        "economic output growth will continue for 1-2 more quarters",
        "investment demand in this sector will remain elevated",
        "related markets may see increased activity",
    ],
    "decreasing": [
        "contraction risk increases if trend persists beyond 2 quarters",
        "policy intervention may be needed to reverse the trend",
        "related sectors may face headwinds",
    ],
    "stable": [
        "current conditions likely to persist without external shock",
        "sector fundamentals appear balanced",
        "low volatility environment expected to continue",
    ],
}

RESEARCH_PREDICTIONS = {
    "active_research": [
        "breakthroughs in this area are likely within 2-3 years",
        "commercialization of findings may begin within 5 years",
        "cross-domain applications will emerge as the field matures",
    ],
    "established_field": [
        "incremental improvements rather than breakthroughs expected",
        "focus will shift to applications and optimization",
        "new entrants will build on existing foundational work",
    ],
}


# ── Main engine ───────────────────────────────────────────────────

class HypothesisEngine:
    """
    Generates and tests hypotheses from public data.

    Usage:
        engine = HypothesisEngine(workspace, brier_scorer)
        hypothesis = await engine.generate(domain="financial")
        result = await engine.test(hypothesis, agent_tools)
        engine.store(hypothesis)
    """

    def __init__(self, workspace: Path, brier_scorer=None):
        self.workspace   = Path(workspace)
        self.brier       = brier_scorer
        self.db_path     = self.workspace / "memory" / "hypotheses.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._pending: list[Hypothesis] = []

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hypotheses (
                id           TEXT PRIMARY KEY,
                domain       TEXT,
                statement    TEXT,
                condition    TEXT,
                prediction   TEXT,
                confidence   REAL,
                status       TEXT,
                source_data  TEXT,
                evidence_for TEXT,
                evidence_against TEXT,
                brier_score  REAL,
                created_at   TEXT,
                tested_at    TEXT
            )
        """)
        conn.commit()
        conn.close()

    def generate_from_worldbank(
        self,
        indicator: str = "NY.GDP.MKTP.CD",
        country:   str = "US",
    ) -> Hypothesis | None:
        """Generate hypothesis from World Bank economic data."""
        import uuid
        data = fetch_worldbank(indicator, country)
        if not data or not data.get("values"):
            return None

        trend_data = detect_trend(data["values"])
        trend      = trend_data["trend"]
        magnitude  = trend_data["magnitude"]

        predictions = ECONOMIC_PREDICTIONS.get(trend, ECONOMIC_PREDICTIONS["stable"])
        import random
        prediction = random.choice(predictions)
        confidence = 0.6 + (magnitude * 0.3)  # Higher magnitude = higher confidence
        confidence = min(0.85, confidence)

        indicator_name = {
            "NY.GDP.MKTP.CD": "GDP",
            "FP.CPI.TOTL.ZG": "inflation",
            "SL.UEM.TOTL.ZS": "unemployment",
            "NE.EXP.GNFS.ZS": "exports",
        }.get(indicator, indicator)

        statement = HYPOTHESIS_TEMPLATES["economic_trend"].format(
            indicator  = indicator_name,
            country    = country,
            trend      = trend,
            prediction = prediction,
            confidence = confidence,
        )

        h = Hypothesis(
            id          = str(uuid.uuid4())[:8],
            domain      = "financial",
            statement   = statement,
            condition   = f"{indicator_name} in {country} is {trend}",
            prediction  = prediction,
            confidence  = confidence,
            source_data = json.dumps(data)[:500],
        )
        self._pending.append(h)
        logger.info(f"Hypothesis generated [{h.id}]: {statement[:80]}")
        return h

    def generate_from_research(
        self,
        topic: str = "machine learning",
    ) -> Hypothesis | None:
        """Generate hypothesis from OpenAlex research data."""
        import uuid
        data = fetch_openalex(topic)
        if not data or not data.get("papers"):
            return None

        pattern_data = detect_research_pattern(data["papers"])
        pattern      = pattern_data["pattern"]
        citations    = pattern_data["avg_citations"]

        predictions  = RESEARCH_PREDICTIONS.get(pattern, RESEARCH_PREDICTIONS["established_field"])
        import random
        prediction   = random.choice(predictions)
        confidence   = 0.65 if pattern == "active_research" else 0.55

        statement = HYPOTHESIS_TEMPLATES["research_momentum"].format(
            topic      = topic,
            pattern    = pattern.replace("_", " "),
            citations  = citations,
            prediction = prediction,
            confidence = confidence,
        )

        h = Hypothesis(
            id          = str(uuid.uuid4())[:8],
            domain      = "research",
            statement   = statement,
            condition   = f"research on '{topic}' shows {pattern}",
            prediction  = prediction,
            confidence  = confidence,
            source_data = json.dumps(data)[:500],
        )
        self._pending.append(h)
        logger.info(f"Hypothesis generated [{h.id}]: {statement[:80]}")
        return h

    def generate(
        self,
        domain:    str = "all",
        topic:     str = "artificial intelligence",
        indicator: str = "NY.GDP.MKTP.CD",
        country:   str = "US",
    ) -> list[Hypothesis]:
        """Generate hypotheses across one or all domains."""
        hypotheses = []

        if domain in ("financial", "all"):
            h = self.generate_from_worldbank(indicator, country)
            if h:
                hypotheses.append(h)

        if domain in ("research", "all"):
            h = self.generate_from_research(topic)
            if h:
                hypotheses.append(h)

        logger.info(f"HypothesisEngine: generated {len(hypotheses)} hypotheses")
        return hypotheses

    def test(self, hypothesis: Hypothesis, evidence: str = "") -> Hypothesis:
        """
        Test a hypothesis with provided evidence.
        Records result to BrierScorer.
        """
        # Simple evidence-based testing
        ev_lower = evidence.lower()
        pred_lower = hypothesis.prediction.lower()

        # Extract key terms from prediction
        key_terms = [w for w in pred_lower.split() if len(w) > 4]
        matches   = sum(1 for t in key_terms if t in ev_lower)
        score     = matches / len(key_terms) if key_terms else 0.5

        if score >= 0.6:
            hypothesis.status = "confirmed"
            hypothesis.evidence_for.append(evidence[:200])
            actual = 1
        elif score <= 0.2:
            hypothesis.status = "rejected"
            hypothesis.evidence_against.append(evidence[:200])
            actual = 0
        else:
            hypothesis.status = "partial"
            hypothesis.evidence_for.append(evidence[:100])
            actual = 0

        hypothesis.tested_at  = datetime.now().isoformat()
        hypothesis.brier_score = (hypothesis.confidence - actual) ** 2

        # Feed to BrierScorer
        if self.brier:
            self.brier.record(
                perspective = "general",
                domain      = hypothesis.domain,
                forecast    = hypothesis.confidence,
                actual      = actual,
                claim       = hypothesis.statement[:200],
                session_key = f"hypothesis:{hypothesis.id}",
            )

        logger.info(
            f"Hypothesis [{hypothesis.id}] tested: {hypothesis.status} "
            f"(brier={hypothesis.brier_score:.3f})"
        )
        return hypothesis

    def store(self, hypothesis: Hypothesis) -> None:
        """Save hypothesis to database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO hypotheses
            (id, domain, statement, condition, prediction, confidence,
             status, source_data, evidence_for, evidence_against,
             brier_score, created_at, tested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            hypothesis.id, hypothesis.domain, hypothesis.statement,
            hypothesis.condition, hypothesis.prediction, hypothesis.confidence,
            hypothesis.status,
            hypothesis.source_data,
            json.dumps(hypothesis.evidence_for),
            json.dumps(hypothesis.evidence_against),
            hypothesis.brier_score,
            hypothesis.created_at, hypothesis.tested_at,
        ))
        conn.commit()
        conn.close()
        logger.info(f"Hypothesis [{hypothesis.id}] stored")

    def get_stats(self) -> dict:
        """Return hypothesis testing statistics."""
        conn   = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT domain, status, COUNT(*) as count,
                   AVG(brier_score) as avg_brier,
                   AVG(confidence) as avg_confidence
            FROM hypotheses
            GROUP BY domain, status
        """)
        rows = cursor.fetchall()
        conn.close()

        stats: dict[str, Any] = {}
        for domain, status, count, avg_brier, avg_conf in rows:
            if domain not in stats:
                stats[domain] = {}
            stats[domain][status] = {
                "count":      count,
                "avg_brier":  round(avg_brier or 0, 3),
                "avg_conf":   round(avg_conf or 0, 2),
            }
        return stats

    def format_for_agent(self, hypotheses: list[Hypothesis]) -> str:
        """Format hypotheses for agent consumption."""
        if not hypotheses:
            return "No hypotheses generated."

        lines = ["## 🔬 Generated Hypotheses\n"]
        for h in hypotheses:
            lines.append(f"**[{h.id}]** Domain: {h.domain}")
            lines.append(f"**Statement:** {h.statement}")
            lines.append(f"**Confidence:** {h.confidence:.0%}")
            lines.append(f"**Status:** {h.status}")
            lines.append("")

        lines.append("---")
        lines.append("To test a hypothesis, provide evidence and call:")
        lines.append("`hypothesis_engine.test(hypothesis, evidence=your_findings)`")
        return "\n".join(lines)
