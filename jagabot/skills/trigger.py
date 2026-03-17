"""
SkillTrigger — auto-detect which financial skill/workflow to activate
based on the user query text and current market conditions.

This is an advisory system: it scores each registered skill against the
incoming context and returns the best match. The agent loop can use this
to pre-select or suggest the right workflow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TriggerRule:
    """One registered trigger for a skill."""

    skill: str
    keywords: list[str]
    conditions: dict[str, Any] = field(default_factory=dict)
    # conditions: {"vix_above": 40, "margin_call": True, ...}


# Default financial triggers
_DEFAULT_TRIGGERS: list[TriggerRule] = [
    TriggerRule(
        skill="crisis_management",
        keywords=[
            "vix", "margin call", "crash", "crisis", "panic",
            "prob_downside", "black swan", "liquidation", "drawdown",
        ],
        conditions={"vix_above": 40},
    ),
    TriggerRule(
        skill="investment_thesis",
        keywords=[
            "new idea", "should i invest", "research", "thesis",
            "opportunity", "buy", "entry point", "undervalued",
        ],
    ),
    TriggerRule(
        skill="portfolio_review",
        keywords=[
            "portfolio", "holdings", "positions", "allocation",
            "exposure", "diversification", "weight",
        ],
    ),
    TriggerRule(
        skill="fund_manager_review",
        keywords=[
            "fund manager", "advisor", "broker", "recommendation",
            "analyst", "tip", "second opinion",
        ],
    ),
    TriggerRule(
        skill="risk_validation",
        keywords=[
            "validate", "check risk", "verify", "backtest",
            "stress test", "what if", "scenario",
        ],
    ),
    TriggerRule(
        skill="rebalancing",
        keywords=[
            "rebalance", "adjust allocation", "trim", "add to position",
            "rotate", "sector rotation", "overweight", "underweight",
        ],
    ),
    TriggerRule(
        skill="skill_creation",
        keywords=[
            "create new analysis", "new skill", "new workflow",
            "custom analysis", "template",
        ],
    ),
    # ── Anthropic Financial Plugin Triggers (v3.8) ───────────────────
    TriggerRule(
        skill="fa-dcf-model",
        keywords=[
            "dcf", "discounted cash flow", "intrinsic value", "wacc",
            "terminal value", "free cash flow", "valuation model",
        ],
    ),
    TriggerRule(
        skill="fa-comps-analysis",
        keywords=[
            "comps", "comparable", "trading multiples", "peer group",
            "ev/ebitda", "p/e ratio", "relative valuation",
        ],
    ),
    TriggerRule(
        skill="fa-lbo-model",
        keywords=[
            "lbo", "leveraged buyout", "buyout model", "debt schedule",
            "sponsor return", "irr target",
        ],
    ),
    TriggerRule(
        skill="fa-3-statements",
        keywords=[
            "3 statements", "three statements", "income statement",
            "balance sheet", "cash flow statement", "financial model",
        ],
    ),
    TriggerRule(
        skill="er-earnings-analysis",
        keywords=[
            "earnings update", "quarterly results", "q1 results", "q2 results",
            "q3 results", "q4 results", "beat miss", "earnings analysis",
        ],
    ),
    TriggerRule(
        skill="er-initiating-coverage",
        keywords=[
            "initiating coverage", "initiate coverage", "coverage report",
            "equity research report", "deep dive",
        ],
    ),
    TriggerRule(
        skill="er-morning-note",
        keywords=[
            "morning note", "morning brief", "daily brief",
            "market open", "pre-market",
        ],
    ),
    TriggerRule(
        skill="er-sector-overview",
        keywords=[
            "sector overview", "industry analysis", "sector analysis",
            "industry trends", "sector performance",
        ],
    ),
    TriggerRule(
        skill="ib-merger-model",
        keywords=[
            "merger model", "m&a model", "accretion dilution",
            "acquisition analysis", "merger analysis",
        ],
    ),
    TriggerRule(
        skill="ib-pitch-deck",
        keywords=[
            "pitch deck", "pitch book", "pitchbook", "client presentation",
            "deal pitch",
        ],
    ),
    TriggerRule(
        skill="ib-cim-builder",
        keywords=[
            "cim", "confidential information memorandum", "offering memorandum",
            "info memo",
        ],
    ),
    TriggerRule(
        skill="pe-ic-memo",
        keywords=[
            "ic memo", "investment committee", "investment memo",
            "deal memo", "committee presentation",
        ],
    ),
    TriggerRule(
        skill="pe-deal-screening",
        keywords=[
            "deal screening", "screen deals", "deal pipeline",
            "deal flow", "opportunity screening",
        ],
    ),
    TriggerRule(
        skill="pe-dd-checklist",
        keywords=[
            "due diligence", "dd checklist", "diligence checklist",
            "dd meeting",
        ],
    ),
    TriggerRule(
        skill="pe-returns-analysis",
        keywords=[
            "irr analysis", "moic", "returns analysis", "fund returns",
            "pe returns", "cash on cash",
        ],
    ),
    TriggerRule(
        skill="wm-client-review",
        keywords=[
            "client review", "client meeting", "wealth review",
            "annual review", "quarterly review client",
        ],
    ),
    TriggerRule(
        skill="wm-financial-plan",
        keywords=[
            "financial plan", "retirement plan", "wealth plan",
            "estate plan", "goal planning",
        ],
    ),
    TriggerRule(
        skill="wm-tax-loss-harvesting",
        keywords=[
            "tax loss", "tax harvest", "tax efficiency",
            "capital gains", "wash sale",
        ],
    ),
    TriggerRule(
        skill="lseg-macro-rates-monitor",
        keywords=[
            "macro rates", "yield curve", "rate monitor",
            "central bank", "fed watch", "interest rate",
        ],
    ),
    TriggerRule(
        skill="lseg-fx-carry-trade",
        keywords=[
            "fx carry", "carry trade", "currency carry",
            "interest rate differential",
        ],
    ),
    TriggerRule(
        skill="lseg-option-vol-analysis",
        keywords=[
            "option vol", "vol surface", "implied volatility",
            "skew analysis", "options analysis",
        ],
    ),
]


class SkillTrigger:
    """Score-based skill detector.

    For each registered trigger the score is:
      keyword_hits + condition_boosts

    The skill with the highest positive score wins.
    If no skill scores > 0, returns 'default'.
    """

    def __init__(self, triggers: list[TriggerRule] | None = None):
        self._triggers: list[TriggerRule] = list(triggers or _DEFAULT_TRIGGERS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, query: str, market_data: dict[str, Any] | None = None) -> dict:
        """Return the best-matching skill for *query* + *market_data*.

        Returns::

            {
                "skill": "crisis_management",
                "score": 7,
                "confidence": 0.85,
                "triggers_matched": ["vix", "margin call"],
                "condition_boosts": ["vix_above:40"],
            }
        """
        market_data = market_data or {}
        query_lower = query.lower()

        best: dict = {
            "skill": "default",
            "score": 0,
            "confidence": 0.0,
            "triggers_matched": [],
            "condition_boosts": [],
        }

        for rule in self._triggers:
            matched_kw = [k for k in rule.keywords if k in query_lower]
            score = len(matched_kw)

            boosts: list[str] = []
            for cond_key, cond_val in rule.conditions.items():
                if self._check_condition(cond_key, cond_val, market_data):
                    score += 5
                    boosts.append(f"{cond_key}:{cond_val}")

            if score > best["score"]:
                max_possible = len(rule.keywords) + 5 * len(rule.conditions)
                confidence = min(score / max(max_possible, 1), 1.0)
                best = {
                    "skill": rule.skill,
                    "score": score,
                    "confidence": round(confidence, 3),
                    "triggers_matched": matched_kw,
                    "condition_boosts": boosts,
                }

        return best

    def register_trigger(
        self,
        skill_name: str,
        keywords: list[str],
        conditions: dict[str, Any] | None = None,
    ) -> TriggerRule:
        """Add a new trigger rule at runtime."""
        rule = TriggerRule(
            skill=skill_name,
            keywords=[k.lower() for k in keywords],
            conditions=conditions or {},
        )
        self._triggers.append(rule)
        return rule

    def get_triggers(self) -> list[dict]:
        """Return all registered triggers as dicts."""
        return [
            {
                "skill": t.skill,
                "keywords": t.keywords,
                "conditions": t.conditions,
            }
            for t in self._triggers
        ]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _check_condition(key: str, threshold: Any, market: dict) -> bool:
        """Evaluate a single market condition."""
        if key.endswith("_above"):
            field_name = key[: -len("_above")]
            return market.get(field_name, 0) > threshold
        if key.endswith("_below"):
            field_name = key[: -len("_below")]
            return market.get(field_name, float("inf")) < threshold
        # Boolean flag (e.g. margin_call=True)
        return bool(market.get(key)) == bool(threshold)
