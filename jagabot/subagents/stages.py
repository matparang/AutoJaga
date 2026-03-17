"""4 stateless stage executors for the subagent pipeline.

Each stage wraps existing jagabot tools, accepts structured input,
and returns structured output.  Stages are stateless — fresh tool
instances are created every call and discarded after.

Pipeline:  WebSearch → Tools → Models → Reasoning
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

from loguru import logger


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class _BaseStage:
    """Common interface for all stages."""

    name: str = ""
    tools_used: list[str] = []
    prompt_file: str = ""

    async def execute(self, data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Stage 1: WebSearch
# ---------------------------------------------------------------------------

class WebSearchStage(_BaseStage):
    """Fetch live market data — prices, VIX, USD, history."""

    name = "websearch"
    tools_used = ["web_search", "yahoo_finance"]
    prompt_file = "websearch.md"

    async def execute(self, data: dict[str, Any]) -> dict[str, Any]:
        """Return market prices.

        Accepts optional ``data["prices"]`` / ``data["vix"]`` overrides so
        the stage can be driven entirely from cached or test data without
        hitting the network.
        """
        assets = data.get("assets", ["WTI", "Brent", "VIX", "USD"])
        now = datetime.now(timezone.utc).isoformat()

        prices: dict[str, float] = {}
        history: dict[str, list[float]] = {}

        # If caller already supplied prices, use them (test / offline mode).
        if "prices" in data and isinstance(data["prices"], dict):
            prices = {k: float(v) for k, v in data["prices"].items()}
        else:
            # Default placeholder prices — real implementation would call
            # yahoo_finance / web_search tools here.
            defaults = {"WTI": 65.0, "Brent": 70.0, "VIX": 25.0, "USD": 104.0}
            for a in assets:
                prices[a] = defaults.get(a, 0.0)

        if "history" in data and isinstance(data["history"], dict):
            history = data["history"]
        else:
            # Synthetic 30-day history for volatility calcs.
            import random
            rng = random.Random(42)
            for a in assets:
                base = prices.get(a, 50.0)
                history[a] = [round(base * (1 + rng.gauss(0, 0.02)), 2) for _ in range(30)]

        return {
            "prices": prices,
            "history": history,
            "source": data.get("source", "default"),
            "timestamp": now,
            "success": True,
        }


# ---------------------------------------------------------------------------
# Stage 2: Tools — financial calculations
# ---------------------------------------------------------------------------

class ToolsStage(_BaseStage):
    """Run monte_carlo, financial_cv, var, cvar, correlation via LabService."""

    name = "tools"
    tools_used = ["monte_carlo", "financial_cv", "var", "cvar", "correlation"]
    prompt_file = "tools.md"

    async def execute(self, data: dict[str, Any]) -> dict[str, Any]:
        from jagabot.lab.service import LabService

        lab = LabService()
        prices = data.get("prices", {})
        history = data.get("history", {})

        current_price = prices.get("WTI", prices.get("Brent", 65.0))
        vix = prices.get("VIX", 25.0)
        volatility = vix / 100.0
        target = data.get("target", current_price * 0.9)

        # ---- Monte Carlo probability ----
        mc_resp = await lab.execute("monte_carlo", {
            "current_price": current_price,
            "target_price": target,
            "vix": vix,
            "days": 30,
            "n_simulations": data.get("simulations", 10000),
        })
        mc_result = mc_resp.get("output", {}) if mc_resp.get("success") else {}

        # ---- Financial CV ----
        changes: list[float] = []
        for asset_hist in history.values():
            if len(asset_hist) >= 2:
                changes = [
                    (asset_hist[i] - asset_hist[i - 1]) / asset_hist[i - 1]
                    for i in range(1, len(asset_hist))
                    if asset_hist[i - 1] != 0
                ]
                break
        if not changes:
            changes = [0.01, -0.02, 0.005, -0.01, 0.015]

        cv_resp = await lab.execute("financial_cv", {
            "method": "calculate_cv",
            "params": {"data": changes},
        })
        cv_result = cv_resp.get("output", {}) if cv_resp.get("success") else {}

        cv_value = cv_result.get("cv", 0.0) if isinstance(cv_result, dict) else 0.0
        if cv_value < 0.2:
            pattern = "STABLE"
        elif cv_value < 0.4:
            pattern = "MODERATE"
        else:
            pattern = "HIGH"

        # ---- VaR ----
        var_resp = await lab.execute("var", {
            "method": "parametric_var",
            "params": {
                "portfolio_value": current_price * 1000,
                "annual_vol": volatility,
                "holding_period": 10,
                "confidence": 0.95,
            },
        })
        var_result = var_resp.get("output", {}) if var_resp.get("success") else {}

        # ---- CVaR ----
        cvar_resp = await lab.execute("cvar", {
            "method": "calculate_cvar",
            "params": {
                "returns": changes,
                "confidence": 0.95,
            },
        })
        cvar_result = cvar_resp.get("output", {}) if cvar_resp.get("success") else {}

        # ---- Correlation ----
        wti_hist = history.get("WTI", changes)
        usd_hist = history.get("USD", changes)
        min_len = min(len(wti_hist), len(usd_hist))
        corr_resp = await lab.execute("correlation", {
            "method": "calculate",
            "params": {
                "series_a": wti_hist[:min_len],
                "series_b": usd_hist[:min_len],
            },
        })
        corr_result = corr_resp.get("output", {}) if corr_resp.get("success") else {}

        return {
            "probability": mc_result,
            "volatility": {
                "cv": cv_value,
                "pattern": pattern,
                "raw": cv_result,
            },
            "var": var_result,
            "cvar": cvar_result,
            "correlation": corr_result,
            "success": True,
        }


# ---------------------------------------------------------------------------
# Stage 3: Models — build integrated models via K1
# ---------------------------------------------------------------------------

class ModelsStage(_BaseStage):
    """Build price, volatility, and economic models using K1 Bayesian."""

    name = "models"
    tools_used = ["k1_bayesian"]
    prompt_file = "models.md"

    async def execute(self, data: dict[str, Any]) -> dict[str, Any]:
        prices = data.get("prices", {})
        probability = data.get("probability", {})
        volatility = data.get("volatility", {})
        correlation = data.get("correlation", {})

        # ---- Price model ----
        prob_value = 0.5
        if isinstance(probability, dict):
            prob_value = probability.get("probability", probability.get("value", 0.5))

        from jagabot.agent.tools.k1_bayesian import K1BayesianTool
        k1 = K1BayesianTool()

        k1_raw = await k1.execute(
            action="update_belief",
            prior=0.5,
            likelihood=prob_value if prob_value else 0.5,
            label="price_direction",
        )
        k1_result = json.loads(k1_raw) if isinstance(k1_raw, str) else k1_raw
        posterior = k1_result.get("posterior", 0.5) if isinstance(k1_result, dict) else 0.5

        if posterior > 0.6:
            direction = "bullish"
        elif posterior < 0.4:
            direction = "bearish"
        else:
            direction = "neutral"

        current_price = prices.get("WTI", prices.get("Brent", 65.0))
        price_model = {
            "direction": direction,
            "confidence": round(abs(posterior - 0.5) * 2, 4),
            "posterior": round(posterior, 4),
            "key_levels": {
                "support": round(current_price * 0.95, 2),
                "resistance": round(current_price * 1.05, 2),
            },
        }

        # ---- Volatility model ----
        cv = volatility.get("cv", 0.25) if isinstance(volatility, dict) else 0.25
        vix = prices.get("VIX", 25.0)
        if cv < 0.2:
            regime = "LOW"
        elif cv < 0.4:
            regime = "MODERATE"
        else:
            regime = "HIGH"

        if vix >= 40:
            vix_level = "panic"
        elif vix >= 25:
            vix_level = "elevated"
        else:
            vix_level = "normal"

        volatility_model = {
            "regime": regime,
            "cv": round(cv, 4),
            "vix": vix,
            "vix_level": vix_level,
            "trend": volatility.get("pattern", "MODERATE") if isinstance(volatility, dict) else "MODERATE",
        }

        # ---- Economic model ----
        usd = prices.get("USD", 104.0)
        if usd >= 110:
            usd_impact = "bearish"
            narrative = "Strong USD pressures commodity prices"
        elif usd <= 95:
            usd_impact = "bullish"
            narrative = "Weak USD supports commodity prices"
        else:
            usd_impact = "neutral"
            narrative = "USD at moderate levels — limited directional bias"

        corr_value = 0.0
        if isinstance(correlation, dict):
            corr_value = correlation.get("correlation", correlation.get("usd_oil", 0.0))

        economic_model = {
            "usd_impact": usd_impact,
            "usd": usd,
            "correlation_strength": round(abs(corr_value), 4),
            "narrative": narrative,
        }

        return {
            "price_model": price_model,
            "volatility_model": volatility_model,
            "economic_model": economic_model,
            "success": True,
        }


# ---------------------------------------------------------------------------
# Stage 4: Reasoning — K3 perspectives + K7 evaluation
# ---------------------------------------------------------------------------

class ReasoningStage(_BaseStage):
    """Apply Bull/Bear/Buffet perspectives and score quality."""

    name = "reasoning"
    tools_used = ["k3_perspective", "evaluation"]
    prompt_file = "reasoning.md"

    async def execute(self, data: dict[str, Any]) -> dict[str, Any]:
        price_model = data.get("price_model", {})
        volatility_model = data.get("volatility_model", {})
        economic_model = data.get("economic_model", {})

        direction = price_model.get("direction", "neutral")
        regime = volatility_model.get("regime", "MODERATE")
        usd_impact = economic_model.get("usd_impact", "neutral")

        # ---- Perspectives ----
        perspectives = {}

        # Bull
        bull_conf = 0.5
        bull_verdict = "HOLD"
        if direction == "bullish":
            bull_conf = 0.7
            bull_verdict = "BUY"
        elif direction == "bearish":
            bull_conf = 0.3
            bull_verdict = "HOLD"
        perspectives["bull"] = {
            "verdict": bull_verdict,
            "confidence": round(bull_conf, 4),
            "rationale": f"Price direction {direction}, volatility {regime}",
        }

        # Bear
        bear_conf = 0.5
        bear_verdict = "HOLD"
        if regime == "HIGH" or direction == "bearish":
            bear_conf = 0.75
            bear_verdict = "SELL"
        elif regime == "LOW" and direction == "bullish":
            bear_conf = 0.25
            bear_verdict = "HOLD"
        perspectives["bear"] = {
            "verdict": bear_verdict,
            "confidence": round(bear_conf, 4),
            "rationale": f"Risk regime {regime}, USD impact {usd_impact}",
        }

        # Buffet
        buffet_conf = 0.5
        buffet_verdict = "HOLD"
        if regime == "HIGH":
            buffet_conf = 0.8
            buffet_verdict = "REDUCE"
        elif direction == "bullish" and regime == "LOW":
            buffet_conf = 0.6
            buffet_verdict = "HOLD"
        perspectives["buffet"] = {
            "verdict": buffet_verdict,
            "confidence": round(buffet_conf, 4),
            "rationale": f"Capital preservation focus — regime {regime}",
        }

        # ---- Weighted collapse (K3 weights: bull=0.3, bear=0.35, buffet=0.35) ----
        weights = {"bull": 0.30, "bear": 0.35, "buffet": 0.35}
        verdict_scores = {"BUY": 1.0, "HOLD": 0.5, "REDUCE": 0.25, "SELL": 0.0}
        weighted_score = sum(
            weights[k] * verdict_scores.get(perspectives[k]["verdict"], 0.5) * perspectives[k]["confidence"]
            for k in weights
        )
        weighted_score = round(weighted_score, 4)

        if weighted_score >= 0.6:
            final_verdict = "BUY"
        elif weighted_score >= 0.35:
            final_verdict = "HOLD"
        elif weighted_score >= 0.2:
            final_verdict = "REDUCE"
        else:
            final_verdict = "SELL"

        # ---- K7 quality score ----
        from jagabot.agent.tools.evaluation import EvaluationTool
        k7 = EvaluationTool()
        score_raw = await k7.execute(
            method="score",
            text=json.dumps({"perspectives": perspectives, "verdict": final_verdict}),
            criteria=["coherence", "completeness", "calibration"],
        )
        score_result = json.loads(score_raw) if isinstance(score_raw, str) else score_raw
        quality_score = 0.75
        if isinstance(score_result, dict):
            quality_score = score_result.get("overall", score_result.get("score", 0.75))

        final_confidence = round(
            sum(perspectives[k]["confidence"] * weights[k] for k in weights), 4
        )

        return {
            "perspectives": perspectives,
            "final": {
                "verdict": final_verdict,
                "confidence": final_confidence,
                "quality_score": round(quality_score, 4),
                "weighted_score": weighted_score,
            },
            "success": True,
        }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_STAGES: dict[str, type[_BaseStage]] = {
    "websearch": WebSearchStage,
    "tools": ToolsStage,
    "models": ModelsStage,
    "reasoning": ReasoningStage,
}
