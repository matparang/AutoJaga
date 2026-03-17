"""Tests for Decision Engine, Education, and Accountability tools."""

import json
import pytest

from jagabot.agent.tools.decision import (
    bull_perspective, bear_perspective, buffet_perspective,
    collapse_perspectives, decision_dashboard, DecisionTool,
)
from jagabot.agent.tools.education import (
    explain_concept, get_glossary, explain_result, EducationTool,
)
from jagabot.agent.tools.accountability import (
    generate_questions, detect_red_flags, generate_report_card, AccountabilityTool,
)
from jagabot.agent.tools.registry import ToolRegistry


# ========================= Decision Engine =========================

class TestBullPerspective:
    def test_strong_buy(self):
        r = bull_perspective(probability_below_target=20, current_price=150, target_price=120)
        assert r["perspective"] == "bull"
        assert r["verdict"] == "STRONG BUY"
        assert r["upside_probability"] == 80

    def test_cautious_hold(self):
        r = bull_perspective(probability_below_target=70, current_price=150, target_price=120)
        assert "HOLD" in r["verdict"] or "CAUTIOUS" in r["verdict"]

    def test_with_cv_and_recovery(self):
        r = bull_perspective(
            probability_below_target=40, current_price=150, target_price=120,
            cv=0.2, recovery_months=3,
        )
        assert len(r["rationale"]) >= 2


class TestBearPerspective:
    def test_sell(self):
        r = bear_perspective(probability_below_target=65, current_price=150, target_price=120)
        assert r["verdict"] == "SELL"
        assert r["downside_probability"] == 65

    def test_hold(self):
        r = bear_perspective(probability_below_target=15, current_price=150, target_price=120)
        assert r["verdict"] == "HOLD"

    def test_with_var_and_warnings(self):
        r = bear_perspective(
            probability_below_target=50, current_price=150, target_price=120,
            var_pct=15.2, cvar_pct=22.1, warnings=["high_cv", "declining_trend"],
            risk_level="high",
        )
        assert len(r["rationale"]) >= 3


class TestBuffetPerspective:
    def test_buy_margin_of_safety(self):
        r = buffet_perspective(
            probability_below_target=20, current_price=100, target_price=80,
            intrinsic_value=160, recovery_months=4,
        )
        assert "Margin of Safety" in r["verdict"] or "BUY" in r["verdict"]
        assert r["margin_of_safety_pct"] > 0

    def test_sell_rule1(self):
        r = buffet_perspective(
            probability_below_target=80, current_price=150, target_price=120,
            intrinsic_value=100,  # overvalued
            recovery_months=30,
        )
        assert "SELL" in r["verdict"] or "REDUCE" in r["verdict"]


class TestCollapsePerspectives:
    def test_consensus_buy(self):
        bull = {"verdict": "STRONG BUY", "confidence": 85}
        bear = {"verdict": "HOLD", "confidence": 40}
        buffet = {"verdict": "BUY — Margin of Safety", "confidence": 75}
        r = collapse_perspectives(bull, bear, buffet)
        assert r["final_verdict"] in ("BUY", "CAUTIOUS BUY")
        assert "weighted_score" in r

    def test_consensus_sell(self):
        bull = {"verdict": "CAUTIOUS HOLD", "confidence": 30}
        bear = {"verdict": "SELL", "confidence": 90}
        buffet = {"verdict": "SELL — Rule #1 Violated", "confidence": 85}
        r = collapse_perspectives(bull, bear, buffet)
        assert r["final_verdict"] in ("SELL", "REDUCE")
        assert r["consensus"] in ("UNANIMOUS SELL", "MAJORITY SELL")

    def test_custom_weights(self):
        bull = {"verdict": "STRONG BUY", "confidence": 90}
        bear = {"verdict": "SELL", "confidence": 90}
        buffet = {"verdict": "HOLD", "confidence": 50}
        r = collapse_perspectives(bull, bear, buffet, weights={"bull": 0.8, "bear": 0.1, "buffet": 0.1})
        assert r["weighted_score"] > 0  # bull-heavy should be positive


class TestDecisionDashboard:
    def test_generates_markdown(self):
        bull = {"verdict": "BUY", "confidence": 70, "rationale": ["Upside strong"]}
        bear = {"verdict": "HEDGE", "confidence": 55, "rationale": ["VaR high"]}
        buffet = {"verdict": "HOLD — Wait for Better Price", "confidence": 60, "rationale": ["MoS low"]}
        collapsed = {"final_verdict": "HOLD", "consensus": "MIXED", "confidence": 62, "weighted_score": -0.1, "weights": {"bull": 0.25, "bear": 0.35, "buffet": 0.4}}
        md = decision_dashboard(bull, bear, buffet, collapsed)
        assert "Decision Dashboard" in md
        assert "BUY" in md
        assert "HEDGE" in md


class TestDecisionTool:
    @pytest.mark.asyncio
    async def test_bull(self):
        tool = DecisionTool()
        result = await tool.execute(method="bull_perspective", params={
            "probability_below_target": 25, "current_price": 150, "target_price": 120
        })
        data = json.loads(result)
        assert data["perspective"] == "bull"

    @pytest.mark.asyncio
    async def test_dashboard(self):
        tool = DecisionTool()
        result = await tool.execute(method="decision_dashboard", params={
            "bull": {"verdict": "BUY", "confidence": 70, "rationale": []},
            "bear": {"verdict": "SELL", "confidence": 80, "rationale": []},
            "buffet": {"verdict": "HOLD", "confidence": 50, "rationale": []},
            "collapsed": {"final_verdict": "HOLD", "consensus": "MIXED", "confidence": 60, "weighted_score": 0, "weights": {"bull": 0.25, "bear": 0.35, "buffet": 0.4}},
        })
        assert "Decision Dashboard" in result


# ========================= Education =========================

class TestExplainConcept:
    def test_english(self):
        r = explain_concept("monte_carlo", "en")
        assert r["title"] == "Monte Carlo Simulation"
        assert "random" in r["explanation"].lower()

    def test_malay(self):
        r = explain_concept("cv", "ms")
        assert r["title"] == "Pekali Variasi (CV)"

    def test_unknown_concept(self):
        r = explain_concept("bogus")
        assert "error" in r

    def test_all_concepts_exist(self):
        for key in ["monte_carlo", "cv", "var", "cvar", "bayesian", "vix", "ci"]:
            r = explain_concept(key)
            assert "title" in r, f"Missing concept: {key}"


class TestGetGlossary:
    def test_full_glossary(self):
        r = get_glossary("en")
        assert r["count"] == 50

    def test_malay_glossary(self):
        r = get_glossary("ms")
        assert r["count"] == 50
        assert r["locale"] == "ms"

    def test_filter(self):
        r = get_glossary("en", filter_terms=["var", "cvar", "vix"])
        assert r["count"] == 3


class TestExplainResult:
    def test_monte_carlo_high_risk(self):
        r = explain_result("monte_carlo", {"probability": 65})
        assert "High risk" in r["interpretation"][0]

    def test_monte_carlo_low_risk(self):
        r = explain_result("monte_carlo", {"probability": 20})
        assert "low risk" in r["interpretation"][0].lower() or "Moderate" in r["interpretation"][0]

    def test_malay(self):
        r = explain_result("monte_carlo", {"probability": 65}, "ms")
        assert "Risiko tinggi" in r["interpretation"][0]


class TestEducationTool:
    @pytest.mark.asyncio
    async def test_dispatch(self):
        tool = EducationTool()
        result = await tool.execute(method="explain_concept", params={"concept": "vix"})
        data = json.loads(result)
        assert "VIX" in data["title"]


# ========================= Accountability =========================

class TestGenerateQuestions:
    def test_high_risk(self):
        r = generate_questions(
            analysis_results={"probability": 45, "var_pct": 15, "risk_level": "high", "warnings": ["high_cv"]},
            recommendation="SELL",
        )
        assert r["total"] > 5
        assert len(r["questions"]["risk"]) >= 2

    def test_malay(self):
        r = generate_questions(
            analysis_results={"probability": 45, "risk_level": "high"},
            locale="ms",
        )
        assert r["locale"] == "ms"
        assert any("risiko" in q.lower() or "analisis" in q.lower() for q in r["questions"]["risk"])


class TestDetectRedFlags:
    def test_guarantee(self):
        r = detect_red_flags(["I guarantee 20% returns annually"])
        assert r["count"] >= 1
        assert r["overall_severity"] == "critical"

    def test_pressure(self):
        r = detect_red_flags(["This is a limited time offer, invest now!"])
        assert r["count"] >= 1

    def test_clean(self):
        r = detect_red_flags(["The fund returned 8% last year, tracking the benchmark."])
        assert r["count"] == 0
        assert r["overall_severity"] == "none"

    def test_malay(self):
        r = detect_red_flags(["Saya jamin pulangan 20%"], locale="ms")
        assert r["count"] >= 1

    def test_contradiction_with_analysis(self):
        r = detect_red_flags(
            ["No risk at all, guaranteed returns"],
            analysis_results={"risk_level": "critical"},
        )
        assert any(f["flag"] == "CONTRADICTION" for f in r["red_flags"])


class TestGenerateReportCard:
    def test_profitable(self):
        r = generate_report_card([
            {"asset": "AAPL", "price": 100, "current_price": 130, "quantity": 10},
            {"asset": "MSFT", "price": 200, "current_price": 250, "quantity": 5},
        ])
        assert r["summary"]["grade"] in ("A", "B")
        assert r["summary"]["total_pnl"] > 0
        assert r["summary"]["win_rate_pct"] == 100

    def test_losing(self):
        r = generate_report_card([
            {"asset": "GRAB", "price": 10, "current_price": 4, "quantity": 100},
        ])
        assert r["summary"]["grade"] in ("D", "F")
        assert r["summary"]["total_pnl"] < 0

    def test_empty(self):
        r = generate_report_card([])
        assert "error" in r


class TestAccountabilityTool:
    @pytest.mark.asyncio
    async def test_dispatch(self):
        tool = AccountabilityTool()
        result = await tool.execute(method="detect_red_flags", params={
            "fund_manager_claims": ["Trust me, no risk"]
        })
        data = json.loads(result)
        assert data["count"] >= 1


# ========================= Full Registration =========================

class TestFullRegistration:
    def test_all_22_tools(self):
        from jagabot.agent.tools import (
            FinancialCVTool, MonteCarloTool, DynamicsTool, StatisticalTool,
            EarlyWarningTool, BayesianTool, CounterfactualTool, SensitivityTool,
            ParetoTool, VisualizationTool,
            VaRTool, CVaRTool, StressTestTool, CorrelationTool, RecoveryTimeTool,
            DecisionTool, EducationTool, AccountabilityTool,
            ResearcherTool, CopywriterTool, SelfImproverTool,
            PortfolioAnalyzerTool,
        )
        reg = ToolRegistry()
        for cls in [
            FinancialCVTool, MonteCarloTool, DynamicsTool, StatisticalTool,
            EarlyWarningTool, BayesianTool, CounterfactualTool, SensitivityTool,
            ParetoTool, VisualizationTool,
            VaRTool, CVaRTool, StressTestTool, CorrelationTool, RecoveryTimeTool,
            DecisionTool, EducationTool, AccountabilityTool,
            ResearcherTool, CopywriterTool, SelfImproverTool,
            PortfolioAnalyzerTool,
        ]:
            reg.register(cls())
        assert len(reg) == 22
