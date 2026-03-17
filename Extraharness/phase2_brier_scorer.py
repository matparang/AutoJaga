# jagabot/kernels/brier_scorer.py
"""
Phase 2 — K1/K3 Bayesian Engine: Automated Brier Scoring

Implements proper probabilistic calibration scoring.
Tracks accuracy per K3 perspective and domain.
Adjusts agent confidence before showing to user.

Formula: Brier Score = (forecast - actual)²
    Perfect: 0.00 (said 100%, was right)
    Random:  0.25 (always says 50%)
    Worst:   1.00 (said 100%, was wrong)

Trust Score = 1 - (avg_brier × 2)
    Brier 0.00 → Trust 1.0 (perfect calibration)
    Brier 0.25 → Trust 0.5 (random baseline)
    Brier 0.50 → Trust 0.0 (worse than random)

Wire into loop.py __init__:
    from jagabot.kernels.brier_scorer import BrierScorer
    self.brier = BrierScorer(workspace / "memory" / "brier.db")

Wire into outcome_tracker.py record_outcome():
    self.brier.record(
        perspective = perspective,
        domain      = topic_tag,
        forecast    = predicted_prob,
        actual      = 1 if result == "correct" else 0,
    )

Wire into loop.py _process_message END:
    # Adjust confidence in final response
    final_content = self.brier.adjust_response_confidence(
        response    = final_content,
        perspective = detected_perspective,
        domain      = detected_topic,
    )
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Config ───────────────────────────────────────────────────────────
MIN_SAMPLES_FOR_TRUST  = 3     # need at least 3 outcomes before adjusting
LOOKBACK_DAYS          = 90    # only use recent outcomes
RANDOM_BRIER           = 0.25  # baseline for a random forecaster
TRUST_THRESHOLD        = 0.50  # below this → flag as unreliable
CONFIDENCE_WORDS = {
    "definitely":   0.95,
    "certainly":    0.92,
    "very likely":  0.85,
    "highly likely":0.85,
    "likely":       0.75,
    "probably":     0.68,
    "possibly":     0.45,
    "unlikely":     0.25,
    "very unlikely":0.10,
}


@dataclass
class CalibrationReport:
    """Calibration report for one perspective + domain."""
    perspective:     str
    domain:          str
    sample_count:    int
    avg_brier:       float
    trust_score:     float
    calibration_gap: float   # avg(forecast) - avg(actual)
    is_reliable:     bool
    recommendation:  str


class BrierScorer:
    """
    Automated Brier Score calibration engine.
    
    Tracks every prediction and outcome.
    Adjusts displayed confidence based on historical accuracy.
    Feeds K3 perspective weight adjustments.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── Public API ───────────────────────────────────────────────────

    def record(
        self,
        perspective:  str,
        domain:       str,
        forecast:     float,   # 0.0 - 1.0
        actual:       int,     # 1 = correct, 0 = wrong
        claim:        str = "",
        session_key:  str = "",
    ) -> float:
        """
        Record a prediction outcome and return its Brier score.
        Call this when OutcomeTracker receives a verdict.
        """
        # Clamp forecast to valid range
        forecast  = max(0.001, min(0.999, forecast))
        brier     = (forecast - actual) ** 2

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO brier_outcomes
            (perspective, domain, forecast, actual,
             brier_score, claim, session_key, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            perspective, domain, forecast, actual,
            brier, claim[:200], session_key,
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()

        logger.info(
            f"BrierScorer: recorded {perspective}/{domain} "
            f"forecast={forecast:.2f} actual={actual} "
            f"brier={brier:.3f}"
        )
        return brier

    def trust_score(
        self,
        perspective: str,
        domain:      str = "general",
    ) -> float:
        """
        Return trust multiplier for a perspective + domain.
        
        1.0 = perfectly calibrated — trust fully
        0.5 = random baseline — halve confidence
        0.0 = worse than random — do not use
        
        Returns None if insufficient data (< MIN_SAMPLES)
        """
        avg_brier, count = self._get_avg_brier(perspective, domain)

        if count < MIN_SAMPLES_FOR_TRUST:
            return None  # not enough data yet

        # Convert Brier to trust: trust = 1 - (brier * 2)
        trust = max(0.0, 1.0 - (avg_brier * 2))
        return round(trust, 3)

    def adjusted_confidence(
        self,
        perspective:    str,
        raw_confidence: float,
        domain:         str = "general",
    ) -> float:
        """
        The key function — multiply raw confidence by trust score.
        
        Agent says: "90% confident" (Bear perspective)
        Bear trust: 0.6 (historical accuracy)
        Shown to user: 90% × 0.6 = 54%
        
        Returns raw_confidence unchanged if insufficient data.
        """
        trust = self.trust_score(perspective, domain)

        if trust is None:
            return raw_confidence  # no data — don't adjust

        adjusted = raw_confidence * trust
        logger.debug(
            f"BrierScorer: {perspective}/{domain} "
            f"raw={raw_confidence:.2f} × trust={trust:.2f} "
            f"= adjusted={adjusted:.2f}"
        )
        return round(adjusted, 3)

    def adjust_response_confidence(
        self,
        response:    str,
        perspective: str,
        domain:      str = "general",
    ) -> str:
        """
        Scan response text for confidence expressions.
        Replace with calibration-adjusted values.
        Add [calibrated] note where adjustments were made.
        """
        trust = self.trust_score(perspective, domain)
        if trust is None or trust >= 0.9:
            return response  # well calibrated or no data — leave as is

        modified = response
        changes  = 0

        # Replace explicit percentages
        def replace_pct(match):
            nonlocal changes
            raw_pct = float(match.group(1)) / 100
            adj_pct = raw_pct * trust
            changes += 1
            return (
                f"{int(adj_pct * 100)}% "
                f"[calibrated from {int(raw_pct * 100)}%]"
            )

        modified = re.sub(
            r'(\d{1,3})%\s*(?=confident|sure|certain|probability)',
            replace_pct,
            modified,
            flags=re.IGNORECASE,
        )

        # Replace confidence words
        for word, raw_prob in CONFIDENCE_WORDS.items():
            if word in modified.lower():
                adj_prob = raw_prob * trust
                adj_word = self._prob_to_word(adj_prob)
                if adj_word != word:
                    modified = re.sub(
                        rf'\b{re.escape(word)}\b',
                        f"{adj_word} [calibrated]",
                        modified,
                        count=1,
                        flags=re.IGNORECASE,
                    )
                    changes += 1

        if changes > 0:
            logger.debug(
                f"BrierScorer: adjusted {changes} confidence "
                f"expression(s) in response "
                f"(trust={trust:.2f} for {perspective}/{domain})"
            )

        return modified

    def get_calibration_report(
        self,
        perspective: str,
        domain:      str = "general",
    ) -> CalibrationReport:
        """
        Return full calibration report for a perspective.
        Used by /status command and KernelHealthMonitor.
        """
        avg_brier, count = self._get_avg_brier(perspective, domain)
        trust            = self.trust_score(perspective, domain)
        cal_gap          = self._get_calibration_gap(
            perspective, domain
        )

        if count < MIN_SAMPLES_FOR_TRUST:
            recommendation = (
                f"Insufficient data ({count}/{MIN_SAMPLES_FOR_TRUST} "
                f"minimum). Record more outcomes to activate."
            )
        elif trust >= 0.8:
            recommendation = "Well calibrated. Trust scores fully."
        elif trust >= 0.5:
            recommendation = (
                f"Moderate calibration. Confidence auto-adjusted "
                f"by ×{trust:.2f}."
            )
        else:
            recommendation = (
                f"Poor calibration. Consider switching to a "
                f"different perspective for this domain."
            )

        return CalibrationReport(
            perspective     = perspective,
            domain          = domain,
            sample_count    = count,
            avg_brier       = round(avg_brier, 4),
            trust_score     = trust or 0.0,
            calibration_gap = round(cal_gap, 4),
            is_reliable     = (trust or 0) >= TRUST_THRESHOLD,
            recommendation  = recommendation,
        )

    def get_all_reports(self) -> list[CalibrationReport]:
        """Return calibration reports for all tracked combinations."""
        conn  = sqlite3.connect(self.db_path)
        rows  = conn.execute("""
            SELECT DISTINCT perspective, domain
            FROM brier_outcomes
        """).fetchall()
        conn.close()

        return [
            self.get_calibration_report(p, d)
            for p, d in rows
        ]

    def format_status(self) -> str:
        """Format calibration status for /status command."""
        reports = self.get_all_reports()

        if not reports:
            return (
                "**Brier Score Calibration**\n\n"
                "No outcomes recorded yet.\n"
                f"Need {MIN_SAMPLES_FOR_TRUST}+ outcomes per "
                "perspective to activate calibration.\n"
                "Give verdict feedback to build history."
            )

        lines = ["**Brier Score Calibration**", ""]
        for r in reports:
            icon  = "✅" if r.is_reliable else "⚠️"
            trust = f"{r.trust_score:.2f}" if r.sample_count >= MIN_SAMPLES_FOR_TRUST else "n/a"
            lines.append(
                f"{icon} **{r.perspective}/{r.domain}** "
                f"brier={r.avg_brier:.3f} "
                f"trust={trust} "
                f"n={r.sample_count}"
            )
            lines.append(f"   → {r.recommendation}")

        return "\n".join(lines)

    # ── Database ─────────────────────────────────────────────────────

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS brier_outcomes (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                perspective  TEXT NOT NULL,
                domain       TEXT NOT NULL DEFAULT 'general',
                forecast     REAL NOT NULL,
                actual       INTEGER NOT NULL,
                brier_score  REAL NOT NULL,
                claim        TEXT DEFAULT '',
                session_key  TEXT DEFAULT '',
                recorded_at  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_perspective_domain
            ON brier_outcomes (perspective, domain, recorded_at)
        """)
        conn.commit()
        conn.close()

    def _get_avg_brier(
        self,
        perspective: str,
        domain:      str,
    ) -> tuple[float, int]:
        """Return (avg_brier_score, sample_count)."""
        cutoff = (
            datetime.now() - timedelta(days=LOOKBACK_DAYS)
        ).isoformat()

        conn = sqlite3.connect(self.db_path)

        # Try domain-specific first
        row = conn.execute("""
            SELECT AVG(brier_score), COUNT(*)
            FROM brier_outcomes
            WHERE perspective = ?
            AND domain = ?
            AND recorded_at > ?
        """, (perspective, domain, cutoff)).fetchone()

        count = row[1] if row else 0

        # Fall back to all domains if insufficient data
        if count < MIN_SAMPLES_FOR_TRUST:
            row = conn.execute("""
                SELECT AVG(brier_score), COUNT(*)
                FROM brier_outcomes
                WHERE perspective = ?
                AND recorded_at > ?
            """, (perspective, cutoff)).fetchone()

        conn.close()
        avg   = row[0] if row and row[0] else RANDOM_BRIER
        count = row[1] if row else 0
        return avg, count

    def _get_calibration_gap(
        self,
        perspective: str,
        domain:      str,
    ) -> float:
        """
        Calibration gap = avg(forecast) - avg(actual).
        Positive = overconfident, Negative = underconfident.
        """
        cutoff = (
            datetime.now() - timedelta(days=LOOKBACK_DAYS)
        ).isoformat()
        conn = sqlite3.connect(self.db_path)
        row  = conn.execute("""
            SELECT AVG(forecast), AVG(actual)
            FROM brier_outcomes
            WHERE perspective = ?
            AND domain = ?
            AND recorded_at > ?
        """, (perspective, domain, cutoff)).fetchone()
        conn.close()

        if not row or row[0] is None:
            return 0.0
        return (row[0] or 0) - (row[1] or 0)

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _prob_to_word(prob: float) -> str:
        """Convert probability back to a confidence word."""
        if prob >= 0.90:
            return "very likely"
        if prob >= 0.75:
            return "likely"
        if prob >= 0.60:
            return "probably"
        if prob >= 0.40:
            return "possibly"
        if prob >= 0.20:
            return "unlikely"
        return "very unlikely"
