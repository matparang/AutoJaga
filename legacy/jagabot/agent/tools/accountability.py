"""Accountability tool — question generator, red flag detector, report card."""

import json
from typing import Any

from jagabot.agent.tools.base import Tool


def generate_questions(
    analysis_results: dict,
    recommendation: str = "",
    locale: str = "en",
) -> dict:
    """Generate smart questions to ask a fund manager based on analysis.

    Args:
        analysis_results: Dict with keys like probability, var_pct, cv, risk_level, warnings.
        recommendation: The current recommendation (buy/sell/hold).
        locale: Language (en, ms).

    Returns:
        dict with categorised questions.
    """
    questions = {"risk": [], "performance": [], "strategy": [], "fees": []}

    prob = analysis_results.get("probability", 0)
    var_pct = analysis_results.get("var_pct", 0)
    cv = analysis_results.get("cv", 0)
    risk_level = analysis_results.get("risk_level", "")
    warnings = analysis_results.get("warnings", [])

    if locale == "ms":
        # Risk questions
        if prob > 30:
            questions["risk"].append(f"Analisis menunjukkan {prob}% kebarangkalian kerugian. Apakah langkah lindung nilai anda?")
        if var_pct and var_pct > 10:
            questions["risk"].append(f"VaR pada {var_pct}% — bagaimana anda menguruskan risiko ekor?")
        if warnings:
            questions["risk"].append(f"Terdapat {len(warnings)} isyarat amaran aktif. Adakah anda sedar tentang ini?")
        if risk_level in ("critical", "high"):
            questions["risk"].append("Tahap risiko adalah TINGGI. Apakah rancangan pengurangan risiko anda?")
        # Performance
        questions["performance"].append("Berapakah pulangan dana berbanding penanda aras dalam 1/3/5 tahun?")
        questions["performance"].append("Berapakah kejatuhan maksimum (drawdown) dalam tempoh 12 bulan lepas?")
        # Strategy
        questions["strategy"].append("Apakah strategi keluar anda jika pasaran jatuh 20%?")
        if recommendation and "SELL" in recommendation.upper():
            questions["strategy"].append("Analisis mencadangkan JUAL. Mengapa anda masih mengekalkan kedudukan ini?")
        # Fees
        questions["fees"].append("Berapakah jumlah yuran pengurusan dan prestasi yang dikenakan?")
        questions["fees"].append("Adakah yuran ini wajar berbanding pulangan yang dihasilkan?")
    else:
        # Risk questions
        if prob > 30:
            questions["risk"].append(f"Analysis shows {prob}% probability of loss. What hedging measures are in place?")
        if var_pct and var_pct > 10:
            questions["risk"].append(f"VaR at {var_pct}% — how are you managing tail risk?")
        if warnings:
            questions["risk"].append(f"There are {len(warnings)} active warning signals. Are you aware of these?")
        if risk_level in ("critical", "high"):
            questions["risk"].append("Risk level is HIGH. What is your risk mitigation plan?")
        # Performance
        questions["performance"].append("What is the fund's return vs benchmark over 1/3/5 years?")
        questions["performance"].append("What was the maximum drawdown in the last 12 months?")
        # Strategy
        questions["strategy"].append("What is your exit strategy if the market drops 20%?")
        if recommendation and "SELL" in recommendation.upper():
            questions["strategy"].append("Analysis suggests SELL. Why are you still holding this position?")
        # Fees
        questions["fees"].append("What are the total management and performance fees charged?")
        questions["fees"].append("Are these fees justified relative to the returns generated?")

    total = sum(len(v) for v in questions.values())
    return {"questions": questions, "total": total, "locale": locale}


def detect_red_flags(
    fund_manager_claims: list[str],
    analysis_results: dict | None = None,
    locale: str = "en",
) -> dict:
    """Detect red flags in fund manager responses.

    Args:
        fund_manager_claims: List of claims/statements from the fund manager.
        analysis_results: Optional analysis results to cross-reference.
        locale: Language (en, ms).

    Returns:
        dict with red_flags list, severity, recommendation.
    """
    red_flags = []

    # Keyword-based red flag patterns
    guarantee_words = ["guarantee", "guaranteed", "pasti", "dijamin", "jamin", "confirm", "sure profit"]
    pressure_words = ["limited time", "last chance", "now or never", "exclusive", "masa terhad", "peluang terakhir"]
    vague_words = ["trust me", "don't worry", "jangan risau", "percaya saya", "complicated"]
    unrealistic_words = ["100%", "no risk", "tiada risiko", "double your money", "gandakan wang"]

    for claim in fund_manager_claims:
        lower = claim.lower()
        if any(w in lower for w in guarantee_words):
            red_flags.append({
                "flag": "GUARANTEED RETURNS" if locale == "en" else "PULANGAN DIJAMIN",
                "severity": "critical",
                "reason": "No investment can guarantee returns. This is a major red flag." if locale == "en"
                         else "Tiada pelaburan boleh menjamin pulangan. Ini bendera merah utama.",
                "claim": claim,
            })
        if any(w in lower for w in pressure_words):
            red_flags.append({
                "flag": "HIGH PRESSURE TACTICS" if locale == "en" else "TAKTIK TEKANAN TINGGI",
                "severity": "high",
                "reason": "Legitimate investments don't require urgency." if locale == "en"
                         else "Pelaburan sah tidak memerlukan keurganan.",
                "claim": claim,
            })
        if any(w in lower for w in vague_words):
            red_flags.append({
                "flag": "VAGUE/DISMISSIVE" if locale == "en" else "KABUR/MENGENEPIKAN",
                "severity": "moderate",
                "reason": "Professionals should explain clearly, not dismiss concerns." if locale == "en"
                         else "Profesional harus menerangkan dengan jelas.",
                "claim": claim,
            })
        if any(w in lower for w in unrealistic_words):
            red_flags.append({
                "flag": "UNREALISTIC PROMISES" if locale == "en" else "JANJI TIDAK REALISTIK",
                "severity": "critical",
                "reason": "Claims of zero risk or doubling money are classic scam indicators." if locale == "en"
                         else "Tuntutan tiada risiko atau gandakan wang adalah petunjuk penipuan.",
                "claim": claim,
            })

    # Cross-reference with analysis
    if analysis_results and red_flags:
        risk = analysis_results.get("risk_level", "")
        if risk in ("critical", "high"):
            red_flags.append({
                "flag": "CONTRADICTION" if locale == "en" else "PERCANGGAHAN",
                "severity": "critical",
                "reason": f"Fund manager claims conflict with {risk} risk analysis." if locale == "en"
                         else f"Tuntutan pengurus dana bercanggah dengan analisis risiko {risk}.",
                "claim": "[system-generated: analysis vs claims mismatch]",
            })

    severity_order = {"critical": 3, "high": 2, "moderate": 1, "low": 0}
    max_sev = max((severity_order.get(f["severity"], 0) for f in red_flags), default=0)
    overall = {3: "critical", 2: "high", 1: "moderate", 0: "none"}.get(max_sev, "none")

    return {
        "red_flags": red_flags,
        "count": len(red_flags),
        "overall_severity": overall,
        "locale": locale,
    }


def generate_report_card(
    decisions: list[dict],
    locale: str = "en",
) -> dict:
    """Generate a performance report card for historical investment decisions.

    Args:
        decisions: List of {date, action, asset, price, current_price, quantity}.
        locale: Language (en, ms).

    Returns:
        dict with metrics, grade, summary.
    """
    if not decisions:
        return {"error": "No decisions provided"}

    total_invested = 0
    total_current = 0
    wins = 0
    losses = 0
    results = []

    for d in decisions:
        qty = d.get("quantity", 1)
        buy_price = d.get("price", 0)
        cur_price = d.get("current_price", buy_price)
        invested = buy_price * qty
        current = cur_price * qty
        pnl = current - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0

        total_invested += invested
        total_current += current
        if pnl >= 0:
            wins += 1
        else:
            losses += 1

        results.append({
            "asset": d.get("asset", "unknown"),
            "action": d.get("action", "buy"),
            "date": d.get("date", ""),
            "buy_price": buy_price,
            "current_price": cur_price,
            "quantity": qty,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })

    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    win_rate = (wins / len(decisions) * 100) if decisions else 0

    # Grade
    if total_pnl_pct >= 15 and win_rate >= 60:
        grade = "A"
    elif total_pnl_pct >= 5 and win_rate >= 50:
        grade = "B"
    elif total_pnl_pct >= 0:
        grade = "C"
    elif total_pnl_pct >= -10:
        grade = "D"
    else:
        grade = "F"

    return {
        "decisions": results,
        "summary": {
            "total_invested": round(total_invested, 2),
            "total_current_value": round(total_current, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(win_rate, 1),
            "grade": grade,
        },
        "locale": locale,
    }


class AccountabilityTool(Tool):
    """Fund manager accountability — questions, red flags, report card."""

    name = "accountability"
    description = (
        "Fund manager accountability tool — helps investors ask the right questions, "
        "detect red flags in fund manager responses, and track decision performance.\n\n"
        "CALL THIS TOOL when the user wants to evaluate their fund manager, "
        "check if claims are trustworthy, or review past investment decisions.\n\n"
        "Methods:\n"
        "- generate_questions: Smart questions based on analysis results (risk, performance, fees)\n"
        "- detect_red_flags: Scan fund manager claims for warning signs (guarantees, pressure, vagueness)\n"
        "- generate_report_card: Grade historical investment decisions with P&L and win rate\n\n"
        "Chain: Run after decision_engine to generate questions about the recommendation. "
        "Pass locale='ms' for Malay output."
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["generate_questions", "detect_red_flags", "generate_report_card"],
                "description": (
                    "generate_questions: needs {analysis_results: {...}, recommendation?, locale?}. "
                    "detect_red_flags: needs {fund_manager_claims: ['...'], analysis_results?, locale?}. "
                    "generate_report_card: needs {decisions: [{date, action, asset, price, current_price, quantity}], locale?}."
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "Keyword arguments. Examples:\n"
                    "generate_questions: {\"analysis_results\": {\"probability\": 45, \"var_pct\": 15, "
                    "\"risk_level\": \"high\"}, \"recommendation\": \"SELL\"}\n"
                    "detect_red_flags: {\"fund_manager_claims\": [\"I guarantee 20% returns\", \"Trust me\"]}\n"
                    "generate_report_card: {\"decisions\": [{\"asset\": \"AAPL\", \"price\": 150, "
                    "\"current_price\": 180, \"quantity\": 10}]}"
                ),
            },
        },
        "required": ["method", "params"],
    }

    _DISPATCH = {
        "generate_questions": generate_questions,
        "detect_red_flags": detect_red_flags,
        "generate_report_card": generate_report_card,
    }

    async def execute(self, **kwargs: Any) -> str:
        method = kwargs.get("method", "")
        params = kwargs.get("params", {})
        fn = self._DISPATCH.get(method)
        if fn is None:
            return json.dumps({"error": f"Unknown method: {method}"})
        try:
            result = fn(**params)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})
