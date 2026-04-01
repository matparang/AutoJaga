# jagabot/swarm/arbitrator.py
"""
Brier-Based Strategy Arbitrator

Resolves strategy conflicts using evidence — not debate.
When two agents disagree on approach, the Arbitrator
picks the one with the lowest historical Brier score.

This replaces expensive LLM-based debate with a
fast, objective, data-driven decision.

The Gemini blueprint suggested using Claude/GPT-5 as
Arbitrator — we use BrierScorer instead:
    - Zero API cost
    - Based on YOUR data, not general LLM
    - Faster (SQLite lookup vs network call)
    - More accurate for your specific domain

Wire into swarm/orchestrator.py (SwarmOrchestrator):
    from jagabot.swarm.arbitrator import StrategyArbitrator
    self.arbitrator = StrategyArbitrator(brier_scorer)

Wire into tri_agent / quad_agent when verification fails:
    if verification_failed and len(strategies) > 1:
        winner = self.arbitrator.arbitrate(strategies)
        proceed_with(winner)

Wire into loop.py when K3 perspectives conflict:
    if bull_verdict != bear_verdict:
        winner = self.arbitrator.arbitrate_perspectives(
            perspectives=[bull_result, bear_result, buffet_result],
            domain=detected_domain,
        )
        final_verdict = winner.verdict
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Strategy dataclass ────────────────────────────────────────────────

@dataclass
class Strategy:
    """
    A strategy/approach being evaluated by the Arbitrator.
    Can represent a K3 perspective, an algorithm choice,
    an analysis method, or a research approach.
    """
    name:        str
    perspective: str            # "bull" | "bear" | "buffet" | "general"
    domain:      str            # "financial" | "research" | etc.
    verdict:     str = ""       # what this strategy recommends
    confidence:  float = 0.5   # raw confidence (0-1)
    evidence:    str = ""       # supporting evidence
    agent_id:    str = ""       # which agent proposed this

    # Set by Arbitrator after evaluation
    trust_score:     float = 0.0
    brier_score:     float = 0.0
    adjusted_conf:   float = 0.0
    arbitration_rank:int   = 0


@dataclass
class ArbitrationResult:
    """Result of one arbitration decision."""
    winner:          Strategy
    losers:          list[Strategy]
    method:          str          # "brier" | "evidence" | "default"
    confidence_gap:  float        # winner vs runner-up trust gap
    explanation:     str
    timestamp:       str = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    was_contested:   bool = False  # True if gap was small

    def format_for_log(self) -> str:
        """Human-readable arbitration summary."""
        return (
            f"Arbitration: {self.winner.name} wins "
            f"(trust={self.winner.trust_score:.2f}) "
            f"over {[l.name for l in self.losers]} "
            f"gap={self.confidence_gap:.2f} "
            f"method={self.method}"
        )


class StrategyArbitrator:
    """
    Evidence-based strategy conflict resolver.
    
    Three resolution methods (in priority order):
    1. BRIER:    pick lowest Brier score (most accurate historically)
    2. EVIDENCE: pick most evidence-backed if Brier data insufficient
    3. DEFAULT:  fall back to Buffet perspective (most conservative)
    
    The Arbitrator is intentionally simple — no AI reasoning,
    just data lookup and comparison. This makes it:
    - Fast (no API calls)
    - Auditable (decision is traceable)
    - Consistent (same input → same output)
    - Cost-free (no model tokens)
    """

    CONTESTED_GAP_THRESHOLD = 0.10   # < 10% gap = contested decision
    MIN_SAMPLES_FOR_BRIER   = 3      # need at least 3 outcomes

    def __init__(
        self,
        brier_scorer: object,
        workspace:    Path = None,
    ) -> None:
        self.brier     = brier_scorer
        self.workspace = workspace
        self._log:     list[ArbitrationResult] = []

    # ── Public API ───────────────────────────────────────────────────

    def arbitrate(
        self,
        strategies: list[Strategy],
    ) -> ArbitrationResult:
        """
        Pick the best strategy from a list.
        Returns ArbitrationResult with winner and explanation.
        """
        if not strategies:
            raise ValueError("arbitrate() requires at least one strategy")

        if len(strategies) == 1:
            return ArbitrationResult(
                winner          = strategies[0],
                losers          = [],
                method          = "default",
                confidence_gap  = 1.0,
                explanation     = "Only one strategy provided.",
            )

        # Enrich each strategy with Brier data
        enriched = [self._enrich(s) for s in strategies]

        # Try Brier-based resolution first
        result = self._resolve_by_brier(enriched)
        if result:
            self._log.append(result)
            self._save_log(result)
            logger.info(result.format_for_log())
            return result

        # Fall back to evidence-based
        result = self._resolve_by_evidence(enriched)
        self._log.append(result)
        self._save_log(result)
        logger.info(result.format_for_log())
        return result

    def arbitrate_perspectives(
        self,
        perspectives:  list[dict],
        domain:        str = "general",
    ) -> ArbitrationResult:
        """
        Convenience method for K3 perspective arbitration.
        
        perspectives: list of {"perspective": "bear", "verdict": "SELL", ...}
        
        Used when Bull/Bear/Buffet disagree on a decision.
        """
        strategies = [
            Strategy(
                name        = p.get("perspective", "general"),
                perspective = p.get("perspective", "general"),
                domain      = domain,
                verdict     = p.get("verdict", ""),
                confidence  = p.get("confidence", 0.5),
                evidence    = p.get("evidence", ""),
            )
            for p in perspectives
        ]
        return self.arbitrate(strategies)

    def arbitrate_agents(
        self,
        agent_outputs: list[dict],
        domain:        str = "general",
    ) -> ArbitrationResult:
        """
        Arbitrate between outputs from multiple agents
        (e.g., tri_agent Worker vs Verifier disagreement).
        
        agent_outputs: list of {
            "agent_id": "worker",
            "strategy": "use CVaR",
            "confidence": 0.8,
            "evidence": "..."
        }
        """
        strategies = [
            Strategy(
                name        = a.get("agent_id", f"agent_{i}"),
                perspective = a.get("perspective", "general"),
                domain      = domain,
                verdict     = a.get("strategy", ""),
                confidence  = a.get("confidence", 0.5),
                evidence    = a.get("evidence", ""),
                agent_id    = a.get("agent_id", ""),
            )
            for i, a in enumerate(agent_outputs)
        ]
        return self.arbitrate(strategies)

    def get_stats(self) -> dict:
        """Return arbitration statistics."""
        if not self._log:
            return {"total_arbitrations": 0}

        methods = {}
        for r in self._log:
            methods[r.method] = methods.get(r.method, 0) + 1

        contested = sum(1 for r in self._log if r.was_contested)

        return {
            "total_arbitrations": len(self._log),
            "by_method":          methods,
            "contested_count":    contested,
            "contested_rate":     contested / len(self._log),
            "most_common_winner": self._most_common_winner(),
        }

    def format_status(self) -> str:
        """Format arbitration status for /status command."""
        stats = self.get_stats()

        if stats["total_arbitrations"] == 0:
            return (
                "**Strategy Arbitrator**\n\n"
                "No arbitrations yet. "
                "Activates when K3 perspectives conflict."
            )

        lines = [
            "**Strategy Arbitrator**",
            "",
            f"Total arbitrations: {stats['total_arbitrations']}",
            f"Contested:          {stats['contested_count']} "
            f"({stats['contested_rate']*100:.0f}%)",
            "",
            "By method:",
        ]
        for method, count in stats["by_method"].items():
            lines.append(f"  {method}: {count}")

        if stats["most_common_winner"]:
            lines.append(
                f"\nMost trusted strategy: "
                f"{stats['most_common_winner']}"
            )

        return "\n".join(lines)

    # ── Resolution methods ───────────────────────────────────────────

    def _resolve_by_brier(
        self,
        strategies: list[Strategy],
    ) -> Optional[ArbitrationResult]:
        """
        Pick strategy with highest trust score (lowest Brier).
        Returns None if insufficient calibration data.
        """
        # Check if we have enough data
        strategies_with_data = [
            s for s in strategies
            if s.trust_score > 0
        ]

        if len(strategies_with_data) < 2:
            return None  # not enough data — try evidence

        # Sort by trust score descending
        ranked = sorted(
            strategies, key=lambda s: s.trust_score, reverse=True
        )

        winner      = ranked[0]
        runner_up   = ranked[1]
        gap         = winner.trust_score - runner_up.trust_score
        is_contested= gap < self.CONTESTED_GAP_THRESHOLD

        # Assign ranks
        for i, s in enumerate(ranked):
            s.arbitration_rank = i + 1

        explanation = (
            f"{winner.name} perspective selected — "
            f"trust score {winner.trust_score:.2f} "
            f"vs {runner_up.name} ({runner_up.trust_score:.2f}). "
            f"Gap: {gap:.2f}."
        )
        if is_contested:
            explanation += (
                f" Note: gap is small ({gap:.2f} < "
                f"{self.CONTESTED_GAP_THRESHOLD}) — "
                f"decision is contested."
            )

        return ArbitrationResult(
            winner          = winner,
            losers          = ranked[1:],
            method          = "brier",
            confidence_gap  = gap,
            explanation     = explanation,
            was_contested   = is_contested,
        )

    def _resolve_by_evidence(
        self,
        strategies: list[Strategy],
    ) -> ArbitrationResult:
        """
        Fall back to evidence-based resolution.
        More evidence = higher score.
        If equal evidence, default to Buffet (most conservative).
        """
        def evidence_score(s: Strategy) -> tuple:
            """Score by evidence length + confidence, Buffet preferred."""
            buffet_bonus = 0.1 if s.perspective == "buffet" else 0.0
            return (
                len(s.evidence) / 100 + s.confidence + buffet_bonus,
            )

        ranked = sorted(strategies, key=evidence_score, reverse=True)
        winner = ranked[0]

        for i, s in enumerate(ranked):
            s.arbitration_rank = i + 1

        method = "evidence" if any(
            len(s.evidence) > 20 for s in strategies
        ) else "default"

        explanation = (
            f"{winner.name} selected by {method}. "
            f"Calibration data insufficient for Brier resolution. "
            f"{'Buffet perspective preferred as most conservative.' if winner.perspective == 'buffet' else ''}"
        )

        return ArbitrationResult(
            winner          = winner,
            losers          = ranked[1:],
            method          = method,
            confidence_gap  = 0.0,
            explanation     = explanation,
            was_contested   = True,  # always contested without Brier data
        )

    # ── Enrichment ───────────────────────────────────────────────────

    def _enrich(self, strategy: Strategy) -> Strategy:
        """Add Brier data to a strategy."""
        if not self.brier:
            return strategy

        try:
            trust = self.brier.trust_score(
                strategy.perspective, strategy.domain
            )
            if trust is not None:
                strategy.trust_score   = trust
                strategy.adjusted_conf = (
                    strategy.confidence * trust
                )
                _, count = self.brier._get_avg_brier(
                    strategy.perspective, strategy.domain
                )
                if count >= self.MIN_SAMPLES_FOR_BRIER:
                    strategy.brier_score = 1 - trust / 2
        except Exception as e:
            logger.debug(f"Arbitrator: enrich failed: {e}")

        return strategy

    # ── Helpers ──────────────────────────────────────────────────────

    def _most_common_winner(self) -> str:
        """Return the most frequently winning strategy name."""
        if not self._log:
            return ""
        counts = {}
        for r in self._log:
            name = r.winner.name
            counts[name] = counts.get(name, 0) + 1
        return max(counts, key=counts.get)

    def _save_log(self, result: ArbitrationResult) -> None:
        """Save arbitration to audit log."""
        if not self.workspace:
            return
        try:
            log_dir  = self.workspace / "memory"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "arbitration_log.jsonl"
            entry = {
                "timestamp":      result.timestamp,
                "winner":         result.winner.name,
                "winner_trust":   result.winner.trust_score,
                "losers":         [l.name for l in result.losers],
                "method":         result.method,
                "gap":            result.confidence_gap,
                "contested":      result.was_contested,
                "explanation":    result.explanation,
            }
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass
