"""Task planner — maps user queries to ordered groups of tool tasks."""

from __future__ import annotations

import re
from typing import Any

from jagabot.swarm.worker_pool import TaskSpec


# ── Query classifiers ─────────────────────────────────────────────────

_PATTERNS: dict[str, list[str]] = {
    "crisis": [
        r"crisis|krisis|crash|meltdown|collapse|kejatuhan",
        r"oil|minyak|wti|brent|crude|mentah",
        r"war|perang|sanction|sekatan",
    ],
    "stock": [
        r"stock|saham|share|equity|ekuiti",
        r"buy|sell|hold|beli|jual|pegang",
        r"dividend|dividen|earnings|pendapatan",
    ],
    "risk": [
        r"risk|risiko|danger|bahaya|volatil",
        r"var\b|cvar|stress.?test|margin.?call",
        r"warning|amaran|alert",
    ],
    "portfolio": [
        r"portfolio|porfolio|allocation|peruntukan",
        r"diversif|korelasi|correlat",
        r"rebalance|imbang",
    ],
    "education": [
        r"explain|terang|what.?is|apa.?itu|maksud",
        r"glossary|glosari|learn|belajar",
    ],
    "accountability": [
        r"fund.?manager|pengurus.?dana|red.?flag",
        r"guarantee|jamin|report.?card",
        r"scam|fraud|tipu",
    ],
    "research": [
        r"trend|tren|scan|imbas|anomal",
        r"regime|pattern|corak",
        r"detect|kesan|unusual|luar.?biasa",
    ],
    "content": [
        r"alert|amaran|notify|maklum",
        r"summary|ringkasan|report|laporan|draft",
        r"improve|perbaik|calibrat|mistake|kesilapan",
    ],
}


def _classify_query(query: str) -> set[str]:
    """Return set of matching categories for the query."""
    q = query.lower()
    matched = set()
    for category, patterns in _PATTERNS.items():
        for pat in patterns:
            if re.search(pat, q):
                matched.add(category)
                break
    return matched or {"general"}


def _detect_params(query: str) -> dict[str, Any]:
    """Extract numeric and structured parameters from query text.

    Supports both structured (TARGET: 80) and natural language patterns.
    All extractors return None on miss so builders can fall back to defaults.
    """
    params: dict[str, Any] = {}

    # Price: RM/USD/$ prefix
    price_match = re.search(r"(?:rm|usd|\$)\s*([\d,.]+)", query, re.I)
    if price_match:
        params["price"] = float(price_match.group(1).replace(",", ""))

    # VIX: "VIX: 35" or "vix=35" or "VIX 35"
    vix_match = re.search(r"vix\s*[=:]?\s*([\d.]+)", query, re.I)
    if vix_match:
        params["vix"] = float(vix_match.group(1))

    # Target price: "TARGET: 80" / "target price 80" / "threshold: 80"
    target_match = re.search(
        r"(?:target|threshold|sasaran)\s*(?:price)?\s*[=:]\s*([\d,.]+)", query, re.I
    )
    if target_match:
        params["target"] = float(target_match.group(1).replace(",", ""))

    # Changes array: "CHANGES: [4.2, 5.1, 6.3]" / "changes=[...]"
    changes_match = re.search(r"changes\s*[=:]\s*\[(.*?)\]", query, re.I)
    if changes_match:
        try:
            params["changes"] = [
                float(x.strip()) for x in changes_match.group(1).split(",") if x.strip()
            ]
        except ValueError:
            pass

    # Stress prices: "STRESS: [75,70,65]" / "stress prices: [...]"
    stress_match = re.search(
        r"stress\s*(?:prices?|scenarios?|levels?)?\s*[=:]\s*\[(.*?)\]", query, re.I
    )
    if stress_match:
        try:
            params["stress_prices"] = [
                float(x.strip()) for x in stress_match.group(1).split(",") if x.strip()
            ]
        except ValueError:
            pass

    # USD Index: "USD Index: 110.5" / "usd_index=110.5" / "DXY: 110.5"
    usd_match = re.search(
        r"(?:usd\s*index|usd_index|dxy)\s*[=:]\s*([\d.]+)", query, re.I
    )
    if usd_match:
        params["usd_index"] = float(usd_match.group(1))

    # Capital: "capital: 500000" / "modal: 500,000"
    capital_match = re.search(
        r"(?:capital|modal|principal)\s*[=:]\s*([\d,.]+)", query, re.I
    )
    if capital_match:
        params["capital"] = float(capital_match.group(1).replace(",", ""))

    # Leverage: "leverage: 2" / "leveraj: 2x"
    leverage_match = re.search(
        r"(?:leverage|leveraj)\s*[=:]\s*([\d.]+)", query, re.I
    )
    if leverage_match:
        params["leverage"] = float(leverage_match.group(1))

    # Exposure: "exposure: 1875000"
    exposure_match = re.search(
        r"exposure\s*[=:]\s*([\d,.]+)", query, re.I
    )
    if exposure_match:
        params["exposure"] = float(exposure_match.group(1).replace(",", ""))

    # Confidence: "confidence: 0.95" / "confidence: 95%"
    conf_match = re.search(r"confidence\s*[=:]\s*([\d.]+)%?", query, re.I)
    if conf_match:
        val = float(conf_match.group(1))
        params["confidence"] = val / 100.0 if val > 1 else val

    # Days / horizon: "days: 30" / "horizon: 10"
    days_match = re.search(r"(?:days|horizon|tempoh)\s*[=:]\s*(\d+)", query, re.I)
    if days_match:
        params["days"] = int(days_match.group(1))

    return params


# ── Plan builders per category ────────────────────────────────────────

def _crisis_tasks(params: dict) -> list[list[TaskSpec]]:
    price = params.get("price", 52.80)
    vix = params.get("vix", 58)
    target = params.get("target", price * 0.85)
    changes = params.get("changes", [0.7, 2.4, 4.2, 6.7, 8.3, 7.4, 5.1, 3.2])
    capital = params.get("capital", 100_000)
    leverage = params.get("leverage", 1)
    exposure = capital * leverage
    confidence = params.get("confidence", 0.95)

    group0 = [
        TaskSpec(tool_name="financial_cv", method="calculate_cv",
                 params={"changes": changes}, group=0),
        TaskSpec(tool_name="monte_carlo", method="__direct__",
                 params={"current_price": price, "target_price": target, "vix": vix}, group=0),
        TaskSpec(tool_name="var", method="parametric_var",
                 params={"mean_return": -0.005, "std_return": 0.03,
                         "portfolio_value": exposure, "confidence": confidence}, group=0),
        TaskSpec(tool_name="cvar", method="calculate_cvar",
                 params={"portfolio_value": exposure,
                         "returns": [-0.03, -0.02, -0.05, -0.01, 0.01, -0.04, -0.02, -0.06, 0.005, -0.035],
                         "confidence": confidence}, group=0),
    ]

    # Stress tests: use extracted prices or derive from current price
    stress_prices = params.get("stress_prices", [])
    if stress_prices:
        stress_tasks = [
            TaskSpec(tool_name="stress_test", method="run_stress_test",
                     params={"portfolio_value": exposure,
                             "scenarios": [{"name": f"stress_{sp}", "shock_pct": round((1 - sp / price) * 100, 1)}]},
                     group=1)
            for sp in stress_prices
        ]
    else:
        stress_tasks = [
            TaskSpec(tool_name="stress_test", method="historical_stress",
                     params={"portfolio_value": exposure, "crisis": "gfc_2008"}, group=1),
        ]

    group1 = [
        TaskSpec(tool_name="early_warning", method="detect_warning_signals",
                 params={"cv": 4.5, "equity_ratio": 0.25, "trend": "declining"}, group=1),
        *stress_tasks,
        TaskSpec(tool_name="recovery_time", method="estimate_recovery",
                 params={"current_value": int(capital * 0.7), "target_value": capital,
                         "monthly_return": 0.02}, group=1),
    ]

    group2 = [
        TaskSpec(tool_name="decision_engine", method="bull_perspective",
                 params={"probability_below_target": 40, "current_price": price,
                         "target_price": target}, group=2),
        TaskSpec(tool_name="decision_engine", method="bear_perspective",
                 params={"probability_below_target": 40, "current_price": price,
                         "target_price": target, "risk_level": "high"}, group=2),
        TaskSpec(tool_name="decision_engine", method="buffet_perspective",
                 params={"probability_below_target": 40, "current_price": price,
                         "target_price": target, "intrinsic_value": price * 1.2}, group=2),
    ]

    return [group0, group1, group2]


def _stock_tasks(params: dict) -> list[list[TaskSpec]]:
    price = params.get("price", 4.50)
    vix = params.get("vix", 28)
    target = params.get("target", price * 0.85)
    changes = params.get("changes", [0.5, 1.2, -0.8, 2.1, -1.5, 0.3, 1.8, -0.4])
    capital = params.get("capital", 100_000)
    leverage = params.get("leverage", 1)
    exposure = capital * leverage
    confidence = params.get("confidence", 0.95)

    group0 = [
        TaskSpec(tool_name="financial_cv", method="calculate_cv",
                 params={"changes": changes}, group=0),
        TaskSpec(tool_name="monte_carlo", method="__direct__",
                 params={"current_price": price, "target_price": target, "vix": vix}, group=0),
        TaskSpec(tool_name="var", method="parametric_var",
                 params={"mean_return": 0.001, "std_return": 0.02,
                         "portfolio_value": exposure, "confidence": confidence}, group=0),
    ]

    group1 = [
        TaskSpec(tool_name="early_warning", method="detect_warning_signals",
                 params={"cv": 2.5, "equity_ratio": 0.4, "trend": "stable"}, group=1),
        TaskSpec(tool_name="decision_engine", method="bull_perspective",
                 params={"probability_below_target": 25, "current_price": price,
                         "target_price": target}, group=1),
        TaskSpec(tool_name="decision_engine", method="bear_perspective",
                 params={"probability_below_target": 25, "current_price": price,
                         "target_price": target}, group=1),
        TaskSpec(tool_name="decision_engine", method="buffet_perspective",
                 params={"probability_below_target": 25, "current_price": price,
                         "target_price": target, "intrinsic_value": price * 1.3}, group=1),
    ]

    return [group0, group1]


def _risk_tasks(params: dict) -> list[list[TaskSpec]]:
    capital = params.get("capital", 100_000)
    leverage = params.get("leverage", 1)
    exposure = capital * leverage
    confidence = params.get("confidence", 0.99)
    usd_index = params.get("usd_index", None)

    # Correlation: use USD index if available, else default series
    if usd_index is not None:
        corr_series_b = [usd_index * (1 + d) for d in [-0.01, 0.005, -0.008, 0.012, -0.003, 0.007, -0.002]]
    else:
        corr_series_b = [2, 3, 4, 5, 6, 5, 4]

    group0 = [
        TaskSpec(tool_name="var", method="parametric_var",
                 params={"mean_return": -0.002, "std_return": 0.025,
                         "portfolio_value": exposure, "confidence": confidence}, group=0),
        TaskSpec(tool_name="cvar", method="calculate_cvar",
                 params={"portfolio_value": exposure,
                         "returns": [-0.03, -0.02, -0.05, -0.01, 0.01, -0.04, -0.02, -0.06, 0.005, -0.035],
                         "confidence": confidence}, group=0),
        TaskSpec(tool_name="stress_test", method="historical_stress",
                 params={"portfolio_value": exposure, "crisis": "gfc_2008"}, group=0),
        TaskSpec(tool_name="correlation", method="pairwise_correlation",
                 params={"series_a": [1, 2, 3, 4, 5, 4, 3],
                         "series_b": corr_series_b,
                         "labels": ["Asset A", "USD Index" if usd_index else "Asset B"]}, group=0),
    ]

    # Add stress scenarios if provided
    stress_prices = params.get("stress_prices", [])
    stress_tasks = []
    if stress_prices:
        price = params.get("price", 100)
        stress_tasks = [
            TaskSpec(tool_name="stress_test", method="run_stress_test",
                     params={"portfolio_value": exposure,
                             "scenarios": [{"name": f"stress_{sp}", "shock_pct": round((1 - sp / price) * 100, 1)}]},
                     group=0)
            for sp in stress_prices
        ]
        group0.extend(stress_tasks)

    group1 = [
        TaskSpec(tool_name="early_warning", method="detect_warning_signals",
                 params={"cv": 5.0, "equity_ratio": 0.2, "trend": "declining"}, group=1),
        TaskSpec(tool_name="recovery_time", method="estimate_recovery",
                 params={"current_value": int(capital * 0.6), "target_value": capital,
                         "monthly_return": 0.015}, group=1),
    ]

    return [group0, group1]


def _portfolio_tasks(params: dict) -> list[list[TaskSpec]]:
    capital = params.get("capital", 100_000)
    leverage = params.get("leverage", 1)
    exposure = capital * leverage
    confidence = params.get("confidence", 0.95)

    group0 = [
        TaskSpec(tool_name="correlation", method="pairwise_correlation",
                 params={"series_a": [100, 102, 98, 105, 103],
                         "series_b": [50, 48, 52, 47, 51],
                         "labels": ["Equity", "Bond"]}, group=0),
        TaskSpec(tool_name="var", method="parametric_var",
                 params={"mean_return": 0.0005, "std_return": 0.015,
                         "portfolio_value": exposure, "confidence": confidence}, group=0),
        TaskSpec(tool_name="sensitivity_analyzer", method="tornado_analysis",
                 params={"base_value": capital,
                         "param_ranges": {
                             "equity_weight": {"low": 0.3, "high": 0.7, "base": 0.5},
                             "bond_weight": {"low": 0.2, "high": 0.5, "base": 0.35},
                         }}, group=0),
        TaskSpec(tool_name="portfolio_analyzer", method="analyze",
                 params={"capital": capital, "leverage": leverage,
                         "positions": [{"symbol": "EQUITY", "entry_price": 100,
                                        "current_price": 105, "quantity": 500, "weight": 0.5},
                                       {"symbol": "BOND", "entry_price": 50,
                                        "current_price": 48, "quantity": 500, "weight": 0.35}],
                         "cash": 0}, group=0),
    ]
    return [group0]


def _education_tasks(params: dict) -> list[list[TaskSpec]]:
    group0 = [
        TaskSpec(tool_name="education", method="explain_concept",
                 params={"concept": "var"}, group=0),
        TaskSpec(tool_name="education", method="explain_concept",
                 params={"concept": "monte_carlo"}, group=0),
        TaskSpec(tool_name="education", method="explain_concept",
                 params={"concept": "cv"}, group=0),
    ]
    return [group0]


def _accountability_tasks(params: dict) -> list[list[TaskSpec]]:
    group0 = [
        TaskSpec(tool_name="accountability", method="detect_red_flags",
                 params={"fund_manager_claims": ["placeholder — override with real claims"]}, group=0),
        TaskSpec(tool_name="accountability", method="generate_questions",
                 params={"analysis_results": {"risk_level": "moderate", "probability": 35}}, group=0),
    ]
    return [group0]


def _research_tasks(params: dict) -> list[list[TaskSpec]]:
    group0 = [
        TaskSpec(tool_name="researcher", method="scan_trends",
                 params={"data_points": [100, 102, 98, 105, 103, 110, 108, 115, 112, 120]}, group=0),
        TaskSpec(tool_name="researcher", method="detect_anomalies",
                 params={"values": [0.01, -0.02, 0.015, -0.08, 0.01, 0.02, -0.01, 0.015]}, group=0),
    ]
    return [group0]


def _content_tasks(params: dict) -> list[list[TaskSpec]]:
    group0 = [
        TaskSpec(tool_name="copywriter", method="draft_alert",
                 params={"risk_level": "moderate", "tool_name": "var", "key_metric": "VaR", "value": 5000}, group=0),
        TaskSpec(tool_name="copywriter", method="draft_report_summary",
                 params={"query": "portfolio analysis", "analysis_results": {}}, group=0),
        TaskSpec(tool_name="self_improver", method="suggest_improvements",
                 params={"analysis_results": {"bias": "neutral", "mae": 0.05}}, group=0),
    ]
    return [group0]


def _general_tasks(params: dict) -> list[list[TaskSpec]]:
    price = params.get("price", 100)
    vix = params.get("vix", 25)
    target = params.get("target", price * 0.90)
    capital = params.get("capital", 100_000)
    leverage = params.get("leverage", 1)
    exposure = capital * leverage
    confidence = params.get("confidence", 0.95)

    group0 = [
        TaskSpec(tool_name="monte_carlo", method="__direct__",
                 params={"current_price": price, "target_price": target, "vix": vix}, group=0),
        TaskSpec(tool_name="var", method="parametric_var",
                 params={"mean_return": 0.0, "std_return": 0.02,
                         "portfolio_value": exposure, "confidence": confidence}, group=0),
    ]
    return [group0]


_PLAN_BUILDERS: dict[str, Any] = {
    "crisis": _crisis_tasks,
    "stock": _stock_tasks,
    "risk": _risk_tasks,
    "portfolio": _portfolio_tasks,
    "education": _education_tasks,
    "accountability": _accountability_tasks,
    "research": _research_tasks,
    "content": _content_tasks,
    "general": _general_tasks,
}


class TaskPlanner:
    """Rule-based planner that converts user queries into ordered task groups."""

    def plan(self, query: str, context: dict[str, Any] | None = None) -> list[list[TaskSpec]]:
        """Plan tasks for a query.

        Returns a list of task groups. Groups execute sequentially;
        tasks within a group run in parallel.
        """
        categories = _classify_query(query)
        params = _detect_params(query)
        if context:
            params.update(context)

        all_groups: list[list[TaskSpec]] = []
        seen_task_keys: set[str] = set()

        for cat in sorted(categories):
            builder = _PLAN_BUILDERS.get(cat, _general_tasks)
            groups = builder(params)
            for group in groups:
                deduped = []
                for task in group:
                    key = f"{task.tool_name}:{task.method}"
                    if key not in seen_task_keys:
                        seen_task_keys.add(key)
                        deduped.append(task)
                if deduped:
                    all_groups.append(deduped)

        return all_groups if all_groups else _general_tasks(params)

    def plan_summary(self, groups: list[list[TaskSpec]]) -> dict[str, Any]:
        """Return a human-readable summary of a plan."""
        total = sum(len(g) for g in groups)
        tools = set()
        for g in groups:
            for t in g:
                tools.add(t.tool_name)
        return {
            "total_tasks": total,
            "groups": len(groups),
            "unique_tools": sorted(tools),
            "parallel_potential": max(len(g) for g in groups) if groups else 0,
        }
