"""Decision engine — Bull/Bear/Buffet 3-perspective analysis with weighted collapse."""

import json
from typing import Any

from jagabot.agent.tools.base import Tool


def bull_perspective(
    probability_below_target: float,
    current_price: float,
    target_price: float,
    cv: float | None = None,
    percentiles: dict | None = None,
    recovery_months: float | None = None,
) -> dict:
    """Optimistic (Bull) perspective — focuses on upside potential.

    Args:
        probability_below_target: P(price < target) from monte_carlo (%).
        current_price: Current price.
        target_price: Target/threshold price.
        cv: Coefficient of variation (optional).
        percentiles: Price percentiles dict e.g. {"p5": 120, "p50": 155, "p95": 200}.
        recovery_months: Estimated recovery time in months.

    Returns:
        dict with verdict, confidence, rationale, upside metrics.
    """
    upside_prob = 100 - probability_below_target
    p95 = percentiles.get("p95", current_price * 1.2) if percentiles else current_price * 1.2
    upside_pct = round((p95 / current_price - 1) * 100, 2)

    if upside_prob >= 70:
        verdict = "STRONG BUY"
        confidence = min(95, upside_prob)
    elif upside_prob >= 50:
        verdict = "BUY"
        confidence = upside_prob
    elif upside_prob >= 35:
        verdict = "HOLD"
        confidence = upside_prob
    else:
        verdict = "CAUTIOUS HOLD"
        confidence = upside_prob

    rationale = []
    rationale.append(f"{upside_prob:.1f}% probability of staying above {target_price}")
    if upside_pct > 20:
        rationale.append(f"Upside potential of {upside_pct}% at 95th percentile")
    if cv and cv < 0.3:
        rationale.append(f"Low volatility (CV={cv:.2f}) — stable asset")
    if recovery_months and recovery_months < 6:
        rationale.append(f"Quick recovery expected ({recovery_months:.0f} months)")

    return {
        "perspective": "bull",
        "verdict": verdict,
        "confidence": round(confidence, 1),
        "upside_probability": round(upside_prob, 2),
        "upside_pct_p95": upside_pct,
        "rationale": rationale,
    }


def bear_perspective(
    probability_below_target: float,
    current_price: float,
    target_price: float,
    var_pct: float | None = None,
    cvar_pct: float | None = None,
    warnings: list[str] | None = None,
    risk_level: str | None = None,
    margin_call: bool | None = None,
    margin_shortfall_ratio: float | None = None,
) -> dict:
    """Pessimistic (Bear) perspective — focuses on downside risk.

    Args:
        probability_below_target: P(price < target) from monte_carlo (%).
        current_price: Current price.
        target_price: Target price.
        var_pct: Value at Risk percentage.
        cvar_pct: Conditional VaR percentage.
        warnings: Warning signals from early_warning tool.
        risk_level: Risk classification (critical/high/moderate/low).
        margin_call: Whether margin call is active — escalates verdict to SELL.
        margin_shortfall_ratio: Margin shortfall as ratio of required margin (e.g. 0.39).

    Returns:
        dict with verdict, confidence, rationale, risk metrics.
    """
    downside_risk = probability_below_target
    # Risk-proportional VaR component (capped at 30% contribution)
    var_adj = min(var_pct or 0, 30) * 0.5

    if margin_call and downside_risk >= 25:
        verdict = "SELL"
        # Calibrated multi-component confidence (Colab v3.7.1)
        var_component = min((var_pct or 0) * 2, 40) * 0.4
        prob_component = downside_risk * 0.3
        if margin_shortfall_ratio is not None:
            shortfall_component = min(margin_shortfall_ratio * 100, 50) * 0.3
        else:
            shortfall_component = downside_risk * 0.5 * 0.3
        confidence = var_component + prob_component + shortfall_component + 15
    elif downside_risk >= 60:
        verdict = "SELL"
        confidence = min(95, downside_risk)
    elif downside_risk >= 40:
        verdict = "REDUCE"
        confidence = downside_risk + 10
    elif downside_risk >= 25:
        verdict = "HEDGE"
        confidence = downside_risk * 0.5 + var_adj
    else:
        verdict = "HOLD"
        confidence = 100 - downside_risk

    rationale = []
    rationale.append(f"{downside_risk:.1f}% probability of falling below {target_price}")
    if var_pct:
        rationale.append(f"VaR: could lose {var_pct:.1f}% in worst case (95% CI)")
    if cvar_pct:
        rationale.append(f"CVaR: average tail loss is {cvar_pct:.1f}%")
    if warnings:
        rationale.append(f"Active warnings: {', '.join(warnings[:3])}")
    if risk_level and risk_level in ("critical", "high"):
        rationale.append(f"Risk level is {risk_level.upper()} — defensive posture needed")

    return {
        "perspective": "bear",
        "verdict": verdict,
        "confidence": round(confidence, 1),
        "downside_probability": round(downside_risk, 2),
        "var_pct": var_pct,
        "cvar_pct": cvar_pct,
        "rationale": rationale,
    }


def buffet_perspective(
    probability_below_target: float,
    current_price: float,
    target_price: float,
    intrinsic_value: float | None = None,
    recovery_months: float | None = None,
    equity: float | None = None,
    debt_ratio: float | None = None,
    margin_call: bool | None = None,
) -> dict:
    """Buffet (Value Investing) perspective — Rule #1: Never lose money.

    Args:
        probability_below_target: P(price < target) from monte_carlo (%).
        current_price: Current price.
        target_price: Target price.
        intrinsic_value: Estimated fair value of the asset.
        recovery_months: Recovery time estimate.
        equity: Current equity position.
        debt_ratio: Debt-to-equity ratio.
        margin_call: Whether margin call is active — triggers Rule #1 violation.

    Returns:
        dict with verdict, confidence, rationale, value metrics.
    """
    if intrinsic_value is None:
        intrinsic_value = target_price * 1.2

    margin_of_safety = (intrinsic_value - current_price) / intrinsic_value if intrinsic_value > 0 else 0
    margin_of_safety_pct = round(margin_of_safety * 100, 2)

    # Margin call override — Rule #1: Never lose money
    if margin_call:
        return {
            "perspective": "buffet",
            "verdict": "SELL — Rule #1 Violated",
            "confidence": 100.0,
            "margin_of_safety_pct": margin_of_safety_pct,
            "intrinsic_value": intrinsic_value,
            "composite_score": 0.0,
            "scores": {
                "rule1_capital_preservation": 0.0,
                "value_gap": 0.0,
                "patience": 0.0,
            },
            "rationale": ["MARGIN CALL ACTIVE — Rule #1: Never lose money"],
        }

    # Buffet weights: margin of safety + capital preservation + long-term view
    rule1_score = 100 - probability_below_target  # capital preservation
    value_score = min(100, max(0, margin_of_safety_pct * 2))  # value gap
    patience_score = 100 - min(100, (recovery_months or 12) * 4)  # recovery patience (penalise >24mo)

    composite = rule1_score * 0.4 + value_score * 0.3 + patience_score * 0.3

    if composite >= 70 and margin_of_safety_pct >= 25:
        verdict = "BUY — Margin of Safety"
        confidence = min(95, composite)
    elif composite >= 55:
        verdict = "HOLD — Wait for Better Price"
        confidence = composite
    elif composite >= 35:
        verdict = "REDUCE — Protect Capital"
        confidence = 100 - composite
    else:
        verdict = "SELL — Rule #1 Violated"
        confidence = 100 - composite

    rationale = []
    rationale.append(f"Margin of safety: {margin_of_safety_pct}%")
    rationale.append(f"Rule #1 (capital preservation): {rule1_score:.0f}/100")
    if recovery_months:
        rationale.append(f"Recovery time: {recovery_months:.0f} months")
    if debt_ratio and debt_ratio > 2:
        rationale.append(f"High debt ratio ({debt_ratio:.1f}) — risk to equity")

    return {
        "perspective": "buffet",
        "verdict": verdict,
        "confidence": round(confidence, 1),
        "margin_of_safety_pct": margin_of_safety_pct,
        "intrinsic_value": intrinsic_value,
        "composite_score": round(composite, 1),
        "scores": {
            "rule1_capital_preservation": round(rule1_score, 1),
            "value_gap": round(value_score, 1),
            "patience": round(patience_score, 1),
        },
        "rationale": rationale,
    }


def collapse_perspectives(
    bull: dict,
    bear: dict,
    buffet: dict,
    weights: dict | None = None,
) -> dict:
    """Collapse 3 perspectives into a final decision via weighted voting.

    Default weights: Buffet 0.4, Bear 0.35, Bull 0.25 (conservative bias).

    Args:
        bull: Bull perspective result.
        bear: Bear perspective result.
        buffet: Buffet perspective result.
        weights: Optional custom weights {bull, bear, buffet}.

    Returns:
        dict with final_verdict, confidence, reasoning.
    """
    w = weights or {"bull": 0.20, "bear": 0.45, "buffet": 0.35}

    # Score each verdict on a -2 to +2 scale
    verdict_scores = {
        "STRONG BUY": 2.0, "BUY": 1.5, "BUY — Margin of Safety": 1.5,
        "HOLD": 0.0, "CAUTIOUS HOLD": -0.5,
        "HOLD — Wait for Better Price": -0.25,
        "HEDGE": -0.5, "REDUCE": -1.0,
        "REDUCE — Protect Capital": -1.0,
        "SELL": -2.0, "SELL — Rule #1 Violated": -2.0,
    }

    bull_score = verdict_scores.get(bull.get("verdict", "HOLD"), 0)
    bear_score = verdict_scores.get(bear.get("verdict", "HOLD"), 0)
    buffet_score = verdict_scores.get(buffet.get("verdict", "HOLD"), 0)

    weighted = (
        w["bull"] * bull_score +
        w["bear"] * bear_score +
        w["buffet"] * buffet_score
    )

    if weighted >= 1.0:
        final_verdict = "BUY"
    elif weighted >= 0.25:
        final_verdict = "CAUTIOUS BUY"
    elif weighted >= -0.25:
        final_verdict = "HOLD"
    elif weighted >= -1.0:
        final_verdict = "REDUCE"
    else:
        final_verdict = "SELL"

    # Consensus check
    verdicts = [bull.get("verdict", ""), bear.get("verdict", ""), buffet.get("verdict", "")]
    buy_count = sum(1 for v in verdicts if "BUY" in v)
    sell_count = sum(1 for v in verdicts if "SELL" in v or "REDUCE" in v)
    if buy_count == 3:
        consensus = "UNANIMOUS BUY"
    elif sell_count == 3:
        consensus = "UNANIMOUS SELL"
    elif buy_count >= 2:
        consensus = "MAJORITY BUY"
    elif sell_count >= 2:
        consensus = "MAJORITY SELL"
    else:
        consensus = "MIXED"

    avg_confidence = (
        w["bull"] * bull.get("confidence", 50) +
        w["bear"] * bear.get("confidence", 50) +
        w["buffet"] * buffet.get("confidence", 50)
    )

    return {
        "final_verdict": final_verdict,
        "consensus": consensus,
        "weighted_score": round(weighted, 3),
        "confidence": round(avg_confidence, 1),
        "weights": w,
        "perspectives": {
            "bull": {"verdict": bull.get("verdict"), "confidence": bull.get("confidence")},
            "bear": {"verdict": bear.get("verdict"), "confidence": bear.get("confidence")},
            "buffet": {"verdict": buffet.get("verdict"), "confidence": buffet.get("confidence")},
        },
    }


def decision_dashboard(
    bull: dict,
    bear: dict,
    buffet: dict,
    collapsed: dict,
) -> str:
    """Format a decision dashboard as markdown.

    Args:
        bull: Bull perspective result.
        bear: Bear perspective result.
        buffet: Buffet perspective result.
        collapsed: Collapsed decision result.

    Returns:
        Markdown-formatted dashboard string.
    """
    lines = [
        "# 🎯 Decision Dashboard",
        "",
        f"## Final Verdict: **{collapsed.get('final_verdict', 'N/A')}**",
        f"Consensus: {collapsed.get('consensus', 'N/A')} | "
        f"Confidence: {collapsed.get('confidence', 0):.1f}%",
        "",
        "---",
        "",
        "| Perspective | Verdict | Confidence |",
        "|------------|---------|------------|",
    ]

    for label, p in [("🐂 Bull", bull), ("🐻 Bear", bear), ("🧓 Buffet", buffet)]:
        lines.append(f"| {label} | {p.get('verdict', 'N/A')} | {p.get('confidence', 0):.1f}% |")

    lines.append("")
    lines.append("### Rationale")
    for label, p in [("Bull", bull), ("Bear", bear), ("Buffet", buffet)]:
        rationale = p.get("rationale", [])
        if rationale:
            lines.append(f"**{label}:** {'; '.join(rationale)}")

    lines.append("")
    ws = collapsed.get("weighted_score", 0)
    lines.append(f"*Weighted score: {ws:.3f} "
                 f"(Bull×{collapsed.get('weights', {}).get('bull', 0.20)} + "
                 f"Bear×{collapsed.get('weights', {}).get('bear', 0.45)} + "
                 f"Buffet×{collapsed.get('weights', {}).get('buffet', 0.35)})*")

    return "\n".join(lines)


class DecisionTool(Tool):
    """3-perspective decision engine: Bull/Bear/Buffet."""

    name = "decision_engine"
    description = (
        "3-perspective financial decision engine — Bull (optimistic), Bear (pessimistic), "
        "Buffet (value investing). CALL THIS TOOL to make a final buy/sell/hold recommendation.\n\n"
        "Methods:\n"
        "- bull_perspective: Optimistic view focusing on upside probability and growth\n"
        "- bear_perspective: Pessimistic view focusing on VaR, CVaR, and warning signals\n"
        "- buffet_perspective: Value investing — margin of safety, Rule #1, recovery time\n"
        "- collapse_perspectives: Weighted voting (Buffet 0.4, Bear 0.35, Bull 0.25) → final verdict\n"
        "- calibrated_decision: All 3 perspectives with adaptive weights from historical accuracy\n"
        "- decision_dashboard: Markdown 3-panel comparison table\n\n"
        "Chain: Run ALL 3 perspectives first, then collapse + dashboard. "
        "Requires monte_carlo probability, and optionally VaR/CVaR/early_warning/recovery_time results."
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": [
                    "bull_perspective", "bear_perspective", "buffet_perspective",
                    "collapse_perspectives", "calibrated_decision", "decision_dashboard",
                ],
                "description": (
                    "bull_perspective: needs {probability_below_target, current_price, target_price, cv?, percentiles?}. "
                    "bear_perspective: needs {probability_below_target, current_price, target_price, var_pct?, cvar_pct?, warnings?, risk_level?, margin_call?}. "
                    "buffet_perspective: needs {probability_below_target, current_price, target_price, intrinsic_value?, recovery_months?, margin_call?}. "
                    "collapse_perspectives: needs {bull: {...}, bear: {...}, buffet: {...}, weights?}. "
                    "decision_dashboard: needs {bull: {...}, bear: {...}, buffet: {...}, collapsed: {...}}."
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "Keyword arguments. Examples:\n"
                    "bull_perspective: {\"probability_below_target\": 29, \"current_price\": 150, \"target_price\": 120}\n"
                    "bear_perspective: {\"probability_below_target\": 29, \"current_price\": 150, \"target_price\": 120, "
                    "\"var_pct\": 15.2, \"warnings\": [\"high_cv\"]}\n"
                    "collapse_perspectives: {\"bull\": {bull_result}, \"bear\": {bear_result}, \"buffet\": {buffet_result}}"
                ),
            },
        },
        "required": ["method", "params"],
    }

    _DISPATCH = {
        "bull_perspective": bull_perspective,
        "bear_perspective": bear_perspective,
        "buffet_perspective": buffet_perspective,
        "collapse_perspectives": collapse_perspectives,
    }
    
    # Valid kwargs for each perspective method
    _VALID_KWARGS = {
        "bull_perspective": {
            "probability_below_target", "current_price", "target_price",
            "cv", "percentiles", "recovery_months",
        },
        "bear_perspective": {
            "probability_below_target", "current_price", "target_price",
            "var_pct", "cvar_pct", "warnings", "risk_level",
            "margin_call", "margin_shortfall_ratio",
        },
        "buffet_perspective": {
            "probability_below_target", "current_price", "target_price",
            "intrinsic_value", "recovery_months", "equity",
            "debt_ratio", "margin_call",
        },
        "collapse_perspectives": {"bull", "bear", "buffet", "weights"},
    }

    async def execute(self, **kwargs: Any) -> str:
        method = kwargs.get("method", "")
        params = kwargs.get("params", {})

        if method == "decision_dashboard":
            try:
                md = decision_dashboard(**params)
                return md
            except Exception as e:
                return json.dumps({"error": str(e)})

        if method == "calibrated_decision":
            try:
                from jagabot.kernels.k3_perspective import K3MultiPerspective
                k3 = K3MultiPerspective()
                result = k3.calibrated_collapse(params)
                return json.dumps(result, default=str)
            except Exception as e:
                return json.dumps({"error": str(e)})

        fn = self._DISPATCH.get(method)
        if fn is None:
            return json.dumps({"error": f"Unknown method: {method}"})
        
        # Filter params to only valid kwargs for this method
        valid = self._VALID_KWARGS.get(method, set())
        filtered_params = {k: v for k, v in params.items() if k in valid}
        
        try:
            result = fn(**filtered_params)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})
