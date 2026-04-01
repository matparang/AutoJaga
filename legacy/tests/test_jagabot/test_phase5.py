"""
Tests for Phase 5 — SkillTrigger, TwoStageReview, SkillComposer,
SkillTriggerTool, ReviewTool.
"""

import asyncio
import json
from unittest.mock import MagicMock

import pytest


def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ====================================================================
# SkillTrigger
# ====================================================================
class TestSkillTrigger:
    def test_crisis_keywords(self):
        from jagabot.skills.trigger import SkillTrigger
        t = SkillTrigger()
        r = t.detect("VIX spiked, expect margin call soon")
        assert r["skill"] == "crisis_management"
        assert "vix" in r["triggers_matched"]
        assert "margin call" in r["triggers_matched"]

    def test_crisis_with_market_boost(self):
        from jagabot.skills.trigger import SkillTrigger
        t = SkillTrigger()
        r = t.detect("VIX is high", {"vix": 50})
        assert r["skill"] == "crisis_management"
        assert r["score"] >= 6  # keyword + condition boost
        assert "vix_above:40" in r["condition_boosts"]

    def test_investment_thesis(self):
        from jagabot.skills.trigger import SkillTrigger
        t = SkillTrigger()
        r = t.detect("should i invest in AAPL?")
        assert r["skill"] == "investment_thesis"

    def test_portfolio_review(self):
        from jagabot.skills.trigger import SkillTrigger
        t = SkillTrigger()
        r = t.detect("show my portfolio allocation")
        assert r["skill"] == "portfolio_review"

    def test_fund_manager(self):
        from jagabot.skills.trigger import SkillTrigger
        t = SkillTrigger()
        r = t.detect("my fund manager gave a recommendation")
        assert r["skill"] == "fund_manager_review"

    def test_risk_validation(self):
        from jagabot.skills.trigger import SkillTrigger
        t = SkillTrigger()
        r = t.detect("validate my risk numbers")
        assert r["skill"] == "risk_validation"

    def test_rebalancing(self):
        from jagabot.skills.trigger import SkillTrigger
        t = SkillTrigger()
        r = t.detect("time to rebalance and adjust allocation")
        assert r["skill"] == "rebalancing"

    def test_skill_creation(self):
        from jagabot.skills.trigger import SkillTrigger
        t = SkillTrigger()
        r = t.detect("I want to create new analysis and a new skill")
        assert r["skill"] == "skill_creation"

    def test_no_match_returns_default(self):
        from jagabot.skills.trigger import SkillTrigger
        t = SkillTrigger()
        r = t.detect("hello world how are you")
        assert r["skill"] == "default"
        assert r["score"] == 0
        assert r["confidence"] == 0.0

    def test_highest_score_wins(self):
        from jagabot.skills.trigger import SkillTrigger
        t = SkillTrigger()
        # crisis has more keyword matches than thesis
        r = t.detect("vix crash panic crisis liquidation drawdown")
        assert r["skill"] == "crisis_management"
        assert r["score"] >= 4

    def test_condition_below(self):
        from jagabot.skills.trigger import SkillTrigger, TriggerRule
        t = SkillTrigger(triggers=[
            TriggerRule(
                skill="cheap_buy",
                keywords=["cheap", "discount"],
                conditions={"price_below": 10},
            )
        ])
        r = t.detect("cheap stock", {"price": 5})
        assert r["skill"] == "cheap_buy"
        assert r["score"] == 6  # 1 keyword + 5 condition

    def test_condition_boolean(self):
        from jagabot.skills.trigger import SkillTrigger, TriggerRule
        t = SkillTrigger(triggers=[
            TriggerRule(
                skill="margin_alert",
                keywords=["margin"],
                conditions={"margin_call": True},
            )
        ])
        r = t.detect("margin check", {"margin_call": True})
        assert r["skill"] == "margin_alert"
        assert len(r["condition_boosts"]) == 1

    def test_register_trigger(self):
        from jagabot.skills.trigger import SkillTrigger
        t = SkillTrigger()
        initial = len(t.get_triggers())
        t.register_trigger("custom_skill", ["xyzunique", "abcspecial"])
        assert len(t.get_triggers()) == initial + 1
        r = t.detect("run xyzunique abcspecial analysis")
        assert r["skill"] == "custom_skill"

    def test_get_triggers(self):
        from jagabot.skills.trigger import SkillTrigger
        t = SkillTrigger()
        triggers = t.get_triggers()
        assert len(triggers) == 28  # 7 original + 21 plugin triggers
        assert all("skill" in tr for tr in triggers)
        assert all("keywords" in tr for tr in triggers)

    def test_empty_query(self):
        from jagabot.skills.trigger import SkillTrigger
        t = SkillTrigger()
        r = t.detect("")
        assert r["skill"] == "default"

    def test_confidence_range(self):
        from jagabot.skills.trigger import SkillTrigger
        t = SkillTrigger()
        r = t.detect("vix crash panic margin call", {"vix": 50})
        assert 0.0 <= r["confidence"] <= 1.0


# ====================================================================
# TwoStageReview
# ====================================================================
class TestTwoStageReview:
    def test_stage1_pass(self):
        from jagabot.skills.review import TwoStageReview
        r = TwoStageReview()
        result = r.stage1_spec(
            {"type": "default"},
            {"action": "buy", "rationale": "cheap"},
        )
        assert result["passed"] is True
        assert result["missing"] == []

    def test_stage1_fail_missing_fields(self):
        from jagabot.skills.review import TwoStageReview
        r = TwoStageReview()
        result = r.stage1_spec(
            {"type": "risk_assessment"},
            {"probability": 0.6},  # missing confidence_interval, action, rationale
        )
        assert result["passed"] is False
        assert "confidence_interval" in result["missing"]
        assert "action" in result["missing"]

    def test_stage1_monte_carlo(self):
        from jagabot.skills.review import TwoStageReview
        r = TwoStageReview()
        result = r.stage1_spec(
            {"type": "monte_carlo"},
            {"probability": 55, "confidence_interval": [50, 60], "simulations": 1000},
        )
        assert result["passed"] is True

    def test_stage1_unknown_type_uses_default(self):
        from jagabot.skills.review import TwoStageReview
        r = TwoStageReview()
        result = r.stage1_spec(
            {"type": "unknown_type"},
            {"action": "hold", "rationale": "stable"},
        )
        assert result["passed"] is True
        assert result["task_type"] == "unknown_type"

    def test_stage2_with_kernel(self):
        from jagabot.skills.review import TwoStageReview
        mock_kernel = MagicMock()
        mock_kernel.evaluate_result.return_value = {"score": 0.85, "details": {}}
        r = TwoStageReview(evaluation_kernel=mock_kernel)
        result = r.stage2_quality(
            {"expected": {"probability": 55}},
            {"probability": 53},
        )
        assert result["passed"] is True
        assert result["score"] == 0.85
        assert result["method"] == "kernel"

    def test_stage2_kernel_low_score_fails(self):
        from jagabot.skills.review import TwoStageReview
        mock_kernel = MagicMock()
        mock_kernel.evaluate_result.return_value = {"score": 0.4, "details": {}}
        r = TwoStageReview(evaluation_kernel=mock_kernel)
        result = r.stage2_quality(
            {"expected": {"probability": 55}},
            {"probability": 20},
        )
        assert result["passed"] is False
        assert result["score"] == 0.4

    def test_stage2_heuristic_fallback(self):
        from jagabot.skills.review import TwoStageReview
        r = TwoStageReview()  # no kernel
        result = r.stage2_quality(
            {"type": "default"},
            {"action": "buy", "rationale": "good", "confidence": 0.8},
        )
        assert result["method"] == "heuristic"
        assert result["score"] == 1.0  # 3/3 populated
        assert result["passed"] is True

    def test_stage2_heuristic_empty_output(self):
        from jagabot.skills.review import TwoStageReview
        r = TwoStageReview()
        result = r.stage2_quality({"type": "default"}, {})
        assert result["passed"] is False
        assert result["score"] == 0.0

    def test_stage2_heuristic_partial(self):
        from jagabot.skills.review import TwoStageReview
        r = TwoStageReview()
        result = r.stage2_quality(
            {},
            {"a": "x", "b": None, "c": "", "d": "y"},  # 2/4 populated
        )
        assert result["score"] == 0.5
        assert result["passed"] is False  # 0.5 < 0.7

    def test_review_both_pass(self):
        from jagabot.skills.review import TwoStageReview
        r = TwoStageReview()
        result = r.review(
            {"type": "default"},
            {"action": "buy", "rationale": "undervalued"},
        )
        assert result["passed"] is True
        assert result["failed_stage"] is None
        assert result["stage1"]["passed"] is True
        assert result["stage2"]["passed"] is True

    def test_review_stage1_fails(self):
        from jagabot.skills.review import TwoStageReview
        r = TwoStageReview()
        result = r.review(
            {"type": "risk_assessment"},
            {"probability": 50},  # missing required fields
        )
        assert result["passed"] is False
        assert result["failed_stage"] == 1
        assert result["stage2"] is None  # skipped

    def test_review_stage2_fails(self):
        from jagabot.skills.review import TwoStageReview
        mock_kernel = MagicMock()
        mock_kernel.evaluate_result.return_value = {"score": 0.3}
        r = TwoStageReview(evaluation_kernel=mock_kernel)
        result = r.review(
            {"type": "default", "expected": {"action": "sell"}},
            {"action": "buy", "rationale": "maybe"},
        )
        assert result["passed"] is False
        assert result["failed_stage"] == 2

    def test_custom_threshold(self):
        from jagabot.skills.review import TwoStageReview
        r = TwoStageReview(quality_threshold=0.3)
        result = r.stage2_quality(
            {},
            {"a": "x", "b": None, "c": "", "d": "y"},  # score=0.5
        )
        assert result["passed"] is True  # 0.5 >= 0.3

    def test_register_spec(self):
        from jagabot.skills.review import TwoStageReview
        r = TwoStageReview()
        r.register_spec("custom_type", ["field_a", "field_b"])
        result = r.stage1_spec({"type": "custom_type"}, {"field_a": 1})
        assert result["passed"] is False
        assert "field_b" in result["missing"]

    def test_get_specs(self):
        from jagabot.skills.review import TwoStageReview
        r = TwoStageReview()
        specs = r.get_specs()
        assert "monte_carlo" in specs
        assert "default" in specs
        assert isinstance(specs["monte_carlo"], list)

    def test_stage2_kernel_exception_fallback(self):
        from jagabot.skills.review import TwoStageReview
        mock_kernel = MagicMock()
        mock_kernel.evaluate_result.side_effect = Exception("boom")
        r = TwoStageReview(evaluation_kernel=mock_kernel)
        result = r.stage2_quality(
            {"expected": {"x": 1}},
            {"x": 1, "y": 2},
        )
        assert result["method"] == "heuristic"


# ====================================================================
# SkillComposer
# ====================================================================
class TestSkillComposer:
    def test_list_workflows(self):
        from jagabot.skills.composer import SkillComposer
        c = SkillComposer()
        wfs = c.list_workflows()
        assert len(wfs) == 4
        names = {w["name"] for w in wfs}
        assert "crisis_management" in names
        assert "investment_thesis" in names
        assert "risk_validation" in names
        assert "portfolio_rebalancing" in names

    def test_get_workflow(self):
        from jagabot.skills.composer import SkillComposer
        c = SkillComposer()
        steps = c.get_workflow("crisis_management")
        assert steps is not None
        assert len(steps) == 5
        assert steps[0]["skill"] == "portfolio_analyzer"

    def test_get_workflow_unknown(self):
        from jagabot.skills.composer import SkillComposer
        c = SkillComposer()
        assert c.get_workflow("nonexistent") is None

    def test_compose(self):
        from jagabot.skills.composer import SkillComposer
        c = SkillComposer()
        plan = c.compose("investment_thesis", {"asset": "AAPL"})
        assert plan["workflow"] == "investment_thesis"
        assert plan["step_count"] == 4
        assert plan["context"]["asset"] == "AAPL"
        assert len(plan["steps"]) == 4

    def test_compose_unknown(self):
        from jagabot.skills.composer import SkillComposer
        c = SkillComposer()
        plan = c.compose("nonexistent")
        assert "error" in plan

    def test_compose_step_ordering(self):
        from jagabot.skills.composer import SkillComposer
        c = SkillComposer()
        plan = c.compose("crisis_management")
        for i, step in enumerate(plan["steps"]):
            assert step["step"] == i

    def test_compose_pass_output_linking(self):
        from jagabot.skills.composer import SkillComposer
        c = SkillComposer()
        plan = c.compose("crisis_management")
        # Step 1 should reference output of step 0
        step1 = plan["steps"][1]
        assert "portfolio_data" in step1["params"]

    def test_register_workflow(self):
        from jagabot.skills.composer import SkillComposer, WorkflowStep
        c = SkillComposer()
        initial = len(c.list_workflows())
        c.register_workflow(
            "custom_wf",
            [WorkflowStep(skill="test_skill", action="run", description="test")],
            description="Custom workflow",
            tags=["custom"],
        )
        assert len(c.list_workflows()) == initial + 1
        steps = c.get_workflow("custom_wf")
        assert len(steps) == 1

    def test_remove_workflow(self):
        from jagabot.skills.composer import SkillComposer
        c = SkillComposer()
        assert c.remove_workflow("crisis_management") is True
        assert c.get_workflow("crisis_management") is None
        assert c.remove_workflow("nonexistent") is False

    def test_workflow_review_flags(self):
        from jagabot.skills.composer import SkillComposer
        c = SkillComposer()
        steps = c.get_workflow("crisis_management")
        review_steps = [s for s in steps if s["review_after"]]
        assert len(review_steps) >= 1


# ====================================================================
# SkillTriggerTool
# ====================================================================
class TestSkillTriggerTool:
    def test_detect(self):
        from jagabot.agent.tools.skill_trigger import SkillTriggerTool
        tool = SkillTriggerTool()
        result = _run(tool.execute(action="detect", query="vix crash margin call"))
        data = json.loads(result)
        assert data["skill"] == "crisis_management"

    def test_detect_with_market(self):
        from jagabot.agent.tools.skill_trigger import SkillTriggerTool
        tool = SkillTriggerTool()
        result = _run(tool.execute(
            action="detect", query="vix alert", market_data={"vix": 50}
        ))
        data = json.loads(result)
        assert data["skill"] == "crisis_management"
        assert data["score"] >= 6

    def test_detect_no_query(self):
        from jagabot.agent.tools.skill_trigger import SkillTriggerTool
        tool = SkillTriggerTool()
        result = _run(tool.execute(action="detect"))
        data = json.loads(result)
        assert "error" in data

    def test_list_triggers(self):
        from jagabot.agent.tools.skill_trigger import SkillTriggerTool
        tool = SkillTriggerTool()
        result = _run(tool.execute(action="list_triggers"))
        data = json.loads(result)
        assert len(data) == 28

    def test_register(self):
        from jagabot.agent.tools.skill_trigger import SkillTriggerTool
        tool = SkillTriggerTool()
        result = _run(tool.execute(
            action="register",
            skill_name="my_custom",
            keywords=["custom", "mine"],
        ))
        data = json.loads(result)
        assert data["registered"] is True
        assert data["skill"] == "my_custom"

    def test_register_missing_params(self):
        from jagabot.agent.tools.skill_trigger import SkillTriggerTool
        tool = SkillTriggerTool()
        result = _run(tool.execute(action="register"))
        data = json.loads(result)
        assert "error" in data

    def test_unknown_action(self):
        from jagabot.agent.tools.skill_trigger import SkillTriggerTool
        tool = SkillTriggerTool()
        result = _run(tool.execute(action="nonexistent"))
        data = json.loads(result)
        assert "error" in data


# ====================================================================
# ReviewTool
# ====================================================================
class TestReviewTool:
    def test_review_pass(self):
        from jagabot.agent.tools.review import ReviewTool
        tool = ReviewTool()
        result = _run(tool.execute(
            action="review",
            task={"type": "default"},
            output={"action": "hold", "rationale": "stable"},
        ))
        data = json.loads(result)
        assert data["passed"] is True

    def test_review_fail_stage1(self):
        from jagabot.agent.tools.review import ReviewTool
        tool = ReviewTool()
        result = _run(tool.execute(
            action="review",
            task={"type": "risk_assessment"},
            output={"probability": 50},
        ))
        data = json.loads(result)
        assert data["passed"] is False
        assert data["failed_stage"] == 1

    def test_spec_check(self):
        from jagabot.agent.tools.review import ReviewTool
        tool = ReviewTool()
        result = _run(tool.execute(
            action="spec_check",
            task={"type": "monte_carlo"},
            output={"probability": 55, "confidence_interval": [50, 60], "simulations": 1000},
        ))
        data = json.loads(result)
        assert data["passed"] is True

    def test_quality_check(self):
        from jagabot.agent.tools.review import ReviewTool
        tool = ReviewTool()
        result = _run(tool.execute(
            action="quality_check",
            task={"type": "default"},
            output={"action": "buy", "rationale": "cheap", "confidence": 0.9},
        ))
        data = json.loads(result)
        assert data["passed"] is True
        assert data["method"] == "heuristic"

    def test_missing_task_output(self):
        from jagabot.agent.tools.review import ReviewTool
        tool = ReviewTool()
        result = _run(tool.execute(action="review", task={}, output={}))
        data = json.loads(result)
        assert "error" in data

    def test_unknown_action(self):
        from jagabot.agent.tools.review import ReviewTool
        tool = ReviewTool()
        result = _run(tool.execute(
            action="nonexistent",
            task={"type": "default"},
            output={"action": "hold"},
        ))
        data = json.loads(result)
        assert "error" in data

    def test_tool_name_and_description(self):
        from jagabot.agent.tools.review import ReviewTool
        tool = ReviewTool()
        assert tool.name == "review"
        assert "two-stage" in tool.description.lower()

    def test_skill_trigger_tool_name(self):
        from jagabot.agent.tools.skill_trigger import SkillTriggerTool
        tool = SkillTriggerTool()
        assert tool.name == "skill_trigger"
        assert "auto-detect" in tool.description.lower()


# ====================================================================
# Tool count assertion
# ====================================================================
class TestPhase5ToolCount:
    def test_all_tools_count(self):
        from jagabot.guardian.tools import ALL_TOOLS
        assert len(ALL_TOOLS) == 32

    def test_exports_count(self):
        from jagabot.agent.tools import __all__
        # 32 tools + Tool + ToolRegistry = 34
        assert len(__all__) == 34
