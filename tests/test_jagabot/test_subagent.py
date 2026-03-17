"""Tests for SubagentManager, stages, and SubagentTool."""

import asyncio
import concurrent.futures
import json
import unittest

from jagabot.subagents.stages import (
    WebSearchStage,
    ToolsStage,
    ModelsStage,
    ReasoningStage,
    ALL_STAGES,
)
from jagabot.subagents.manager import SubagentManager, STAGE_ORDER
from jagabot.agent.tools.subagent import SubagentTool


def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ===================================================================
# Sample data fixtures
# ===================================================================

SAMPLE_PRICES = {"WTI": 65.0, "Brent": 70.0, "VIX": 25.0, "USD": 104.0}

SAMPLE_HISTORY = {
    "WTI": [64 + i * 0.1 for i in range(30)],
    "Brent": [69 + i * 0.1 for i in range(30)],
    "VIX": [24 + i * 0.05 for i in range(30)],
    "USD": [103 + i * 0.03 for i in range(30)],
}

SAMPLE_WEB_DATA = {
    "prices": SAMPLE_PRICES,
    "history": SAMPLE_HISTORY,
    "source": "test",
}


# ===================================================================
# WebSearchStage tests
# ===================================================================

class TestWebSearchStage(unittest.TestCase):

    def test_name(self):
        assert WebSearchStage.name == "websearch"

    def test_tools_used(self):
        assert "web_search" in WebSearchStage.tools_used

    def test_execute_with_prices(self):
        stage = WebSearchStage()
        result = _run(stage.execute({"prices": SAMPLE_PRICES}))
        assert result["success"] is True
        assert result["prices"]["WTI"] == 65.0
        assert "timestamp" in result

    def test_execute_default_prices(self):
        stage = WebSearchStage()
        result = _run(stage.execute({}))
        assert result["success"] is True
        assert "WTI" in result["prices"]

    def test_execute_with_history(self):
        stage = WebSearchStage()
        result = _run(stage.execute({"prices": SAMPLE_PRICES, "history": SAMPLE_HISTORY}))
        assert len(result["history"]["WTI"]) == 30

    def test_execute_generates_history(self):
        stage = WebSearchStage()
        result = _run(stage.execute({"prices": SAMPLE_PRICES}))
        assert len(result["history"]["WTI"]) == 30

    def test_custom_assets(self):
        stage = WebSearchStage()
        result = _run(stage.execute({"assets": ["WTI"], "prices": {"WTI": 60.0}}))
        assert "WTI" in result["prices"]

    def test_stateless(self):
        s1 = WebSearchStage()
        s2 = WebSearchStage()
        r1 = _run(s1.execute({"prices": SAMPLE_PRICES, "history": SAMPLE_HISTORY}))
        r2 = _run(s2.execute({"prices": SAMPLE_PRICES, "history": SAMPLE_HISTORY}))
        assert r1["prices"] == r2["prices"]


# ===================================================================
# ToolsStage tests
# ===================================================================

class TestToolsStage(unittest.TestCase):

    def test_name(self):
        assert ToolsStage.name == "tools"

    def test_tools_used(self):
        assert "monte_carlo" in ToolsStage.tools_used
        assert "var" in ToolsStage.tools_used

    def test_execute_basic(self):
        stage = ToolsStage()
        result = _run(stage.execute({
            "prices": SAMPLE_PRICES,
            "history": SAMPLE_HISTORY,
        }))
        assert result["success"] is True
        assert "probability" in result
        assert "volatility" in result
        assert "var" in result
        assert "cvar" in result
        assert "correlation" in result

    def test_volatility_pattern(self):
        stage = ToolsStage()
        result = _run(stage.execute({
            "prices": SAMPLE_PRICES,
            "history": SAMPLE_HISTORY,
        }))
        assert result["volatility"]["pattern"] in ("STABLE", "MODERATE", "HIGH")

    def test_no_history_fallback(self):
        stage = ToolsStage()
        result = _run(stage.execute({"prices": SAMPLE_PRICES}))
        assert result["success"] is True

    def test_custom_target(self):
        stage = ToolsStage()
        result = _run(stage.execute({
            "prices": SAMPLE_PRICES,
            "history": SAMPLE_HISTORY,
            "target": 60.0,
        }))
        assert result["success"] is True


# ===================================================================
# ModelsStage tests
# ===================================================================

class TestModelsStage(unittest.TestCase):

    def test_name(self):
        assert ModelsStage.name == "models"

    def test_tools_used(self):
        assert "k1_bayesian" in ModelsStage.tools_used

    def test_execute_basic(self):
        stage = ModelsStage()
        result = _run(stage.execute({
            "prices": SAMPLE_PRICES,
            "probability": {"probability": 0.6},
            "volatility": {"cv": 0.3, "pattern": "MODERATE"},
            "correlation": {"correlation": -0.4},
        }))
        assert result["success"] is True
        assert "price_model" in result
        assert "volatility_model" in result
        assert "economic_model" in result

    def test_price_model_direction(self):
        stage = ModelsStage()
        result = _run(stage.execute({
            "prices": SAMPLE_PRICES,
            "probability": {"probability": 0.8},
        }))
        assert result["price_model"]["direction"] in ("bullish", "bearish", "neutral")

    def test_volatility_model_regime(self):
        stage = ModelsStage()
        result = _run(stage.execute({
            "prices": {"WTI": 65.0, "VIX": 45.0},
            "volatility": {"cv": 0.5},
        }))
        assert result["volatility_model"]["regime"] == "HIGH"
        assert result["volatility_model"]["vix_level"] == "panic"

    def test_economic_model_strong_usd(self):
        stage = ModelsStage()
        result = _run(stage.execute({
            "prices": {"WTI": 65.0, "USD": 115.0, "VIX": 20.0},
        }))
        assert result["economic_model"]["usd_impact"] == "bearish"

    def test_economic_model_weak_usd(self):
        stage = ModelsStage()
        result = _run(stage.execute({
            "prices": {"WTI": 65.0, "USD": 90.0, "VIX": 20.0},
        }))
        assert result["economic_model"]["usd_impact"] == "bullish"

    def test_key_levels(self):
        stage = ModelsStage()
        result = _run(stage.execute({"prices": {"WTI": 100.0, "VIX": 20.0}}))
        assert result["price_model"]["key_levels"]["support"] == 95.0
        assert result["price_model"]["key_levels"]["resistance"] == 105.0


# ===================================================================
# ReasoningStage tests
# ===================================================================

class TestReasoningStage(unittest.TestCase):

    def test_name(self):
        assert ReasoningStage.name == "reasoning"

    def test_tools_used(self):
        assert "k3_perspective" in ReasoningStage.tools_used
        assert "evaluation" in ReasoningStage.tools_used

    def test_execute_basic(self):
        stage = ReasoningStage()
        result = _run(stage.execute({
            "price_model": {"direction": "bearish"},
            "volatility_model": {"regime": "HIGH"},
            "economic_model": {"usd_impact": "bearish"},
        }))
        assert result["success"] is True
        assert "perspectives" in result
        assert "final" in result
        assert "bull" in result["perspectives"]
        assert "bear" in result["perspectives"]
        assert "buffet" in result["perspectives"]

    def test_final_has_required_fields(self):
        stage = ReasoningStage()
        result = _run(stage.execute({
            "price_model": {"direction": "neutral"},
            "volatility_model": {"regime": "MODERATE"},
            "economic_model": {"usd_impact": "neutral"},
        }))
        final = result["final"]
        assert "verdict" in final
        assert "confidence" in final
        assert "quality_score" in final
        assert "weighted_score" in final

    def test_bearish_leans_sell(self):
        stage = ReasoningStage()
        result = _run(stage.execute({
            "price_model": {"direction": "bearish"},
            "volatility_model": {"regime": "HIGH"},
            "economic_model": {"usd_impact": "bearish"},
        }))
        # Bear + Buffet should dominate with SELL/REDUCE
        assert result["perspectives"]["bear"]["verdict"] == "SELL"
        assert result["perspectives"]["buffet"]["verdict"] == "REDUCE"

    def test_bullish_leans_buy(self):
        stage = ReasoningStage()
        result = _run(stage.execute({
            "price_model": {"direction": "bullish"},
            "volatility_model": {"regime": "LOW"},
            "economic_model": {"usd_impact": "bullish"},
        }))
        assert result["perspectives"]["bull"]["verdict"] == "BUY"

    def test_verdict_values(self):
        stage = ReasoningStage()
        result = _run(stage.execute({
            "price_model": {"direction": "neutral"},
            "volatility_model": {"regime": "MODERATE"},
            "economic_model": {"usd_impact": "neutral"},
        }))
        assert result["final"]["verdict"] in ("BUY", "HOLD", "REDUCE", "SELL")


# ===================================================================
# ALL_STAGES registry
# ===================================================================

class TestStageRegistry(unittest.TestCase):

    def test_four_stages(self):
        assert len(ALL_STAGES) == 4

    def test_stage_names(self):
        assert set(ALL_STAGES.keys()) == {"websearch", "tools", "models", "reasoning"}


# ===================================================================
# SubagentManager tests
# ===================================================================

class TestSubagentManager(unittest.TestCase):

    def setUp(self):
        self.mgr = SubagentManager()

    def test_prompts_loaded(self):
        assert len(self.mgr.prompts) == 4
        for name in STAGE_ORDER:
            assert name in self.mgr.prompts
            assert len(self.mgr.prompts[name]) > 50

    def test_get_prompt(self):
        prompt = self.mgr.get_prompt("websearch")
        assert "WebSearch" in prompt

    def test_get_prompt_unknown(self):
        assert self.mgr.get_prompt("bad") is None

    def test_get_stages(self):
        stages = self.mgr.get_stages()
        assert len(stages) == 4
        assert stages[0]["name"] == "websearch"
        assert stages[3]["name"] == "reasoning"

    def test_execute_stage_websearch(self):
        result = _run(self.mgr.execute_stage("websearch", {"prices": SAMPLE_PRICES}))
        assert result["success"] is True

    def test_execute_stage_unknown(self):
        result = _run(self.mgr.execute_stage("bad_stage", {}))
        assert result["success"] is False
        assert "Unknown stage" in result["error"]

    def test_execute_workflow(self):
        result = _run(self.mgr.execute_workflow(
            query="Oil crisis analysis",
            data={"prices": SAMPLE_PRICES, "history": SAMPLE_HISTORY},
        ))
        assert result["success"] is True
        assert "websearch" in result
        assert "tools" in result
        assert "models" in result
        assert "reasoning" in result
        assert "elapsed_s" in result
        assert result["reasoning"]["success"] is True

    def test_workflow_has_final_verdict(self):
        result = _run(self.mgr.execute_workflow(
            data={"prices": SAMPLE_PRICES, "history": SAMPLE_HISTORY},
        ))
        assert "final" in result["reasoning"]
        assert result["reasoning"]["final"]["verdict"] in ("BUY", "HOLD", "REDUCE", "SELL")

    def test_workflow_stateless(self):
        data = {"prices": SAMPLE_PRICES, "history": SAMPLE_HISTORY}
        r1 = _run(self.mgr.execute_workflow(data=data))
        r2 = _run(self.mgr.execute_workflow(data=data))
        assert r1["reasoning"]["final"]["verdict"] == r2["reasoning"]["final"]["verdict"]


# ===================================================================
# SubagentTool tests
# ===================================================================

class TestSubagentTool(unittest.TestCase):

    def setUp(self):
        self.tool = SubagentTool()

    def test_tool_name(self):
        assert self.tool.name == "subagent"

    def test_tool_schema(self):
        assert "action" in self.tool.parameters["properties"]

    def test_list_stages_action(self):
        result = json.loads(_run(self.tool.execute(action="list_stages")))
        assert len(result) == 4
        assert result[0]["name"] == "websearch"

    def test_get_stage_prompt_action(self):
        result = json.loads(_run(self.tool.execute(
            action="get_stage_prompt", stage="reasoning",
        )))
        assert "Reasoning" in result["prompt"]

    def test_get_stage_prompt_missing(self):
        result = json.loads(_run(self.tool.execute(action="get_stage_prompt")))
        assert "error" in result

    def test_get_stage_prompt_unknown(self):
        result = json.loads(_run(self.tool.execute(
            action="get_stage_prompt", stage="bad",
        )))
        assert "error" in result

    def test_run_stage_action(self):
        result = json.loads(_run(self.tool.execute(
            action="run_stage", stage="websearch",
            data={"prices": SAMPLE_PRICES},
        )))
        assert result["success"] is True

    def test_run_stage_missing_stage(self):
        result = json.loads(_run(self.tool.execute(action="run_stage")))
        assert "error" in result

    def test_run_workflow_action(self):
        result = json.loads(_run(self.tool.execute(
            action="run_workflow",
            query="Test analysis",
            data={"prices": SAMPLE_PRICES, "history": SAMPLE_HISTORY},
        )))
        assert result["success"] is True
        assert "reasoning" in result

    def test_unknown_action(self):
        result = json.loads(_run(self.tool.execute(action="bad")))
        assert "error" in result


if __name__ == "__main__":
    unittest.main()
