"""MetaLearning tool — self-improvement engine with experiment tracking."""

import json
from typing import Any

from jagabot.agent.tools.base import Tool
from jagabot.engines.meta_learning import MetaLearningEngine
from jagabot.engines.experiment_tracker import ExperimentTracker


class MetaLearningTool(Tool):
    """Self-improvement engine with strategy tracking and experiment management."""

    name = "meta_learning"
    description = (
        "Self-improvement engine — tracks analysis strategy outcomes, detects learning problems, "
        "applies meta-fixes, and manages structured experiments.\n\n"
        "Actions:\n"
        "- record_result: Record outcome of an analysis strategy (bull/bear/buffet/risk/etc.)\n"
        "- select_strategy: Pick best strategy based on historical performance\n"
        "- detect_problems: Scan for systemic learning issues\n"
        "- meta_cycle: Full meta-analysis cycle (detect + fix)\n"
        "- get_status: Current learning health metrics\n"
        "- get_rankings: Strategy performance rankings\n"
        "- create_experiment: Register a hypothesis for testing\n"
        "- complete_experiment: Record experiment results\n"
        "- list_experiments: List experiments by status\n"
        "- experiment_summary: Experiment statistics\n\n"
        "Chain: After decision_engine analysis, use record_result to log outcome. "
        "Use create_experiment before testing a new approach, complete_experiment after."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "record_result", "select_strategy", "detect_problems",
                    "meta_cycle", "get_status", "get_rankings",
                    "create_experiment", "complete_experiment",
                    "list_experiments", "experiment_summary",
                ],
                "description": (
                    "record_result: {strategy, success, fitness_gain?}. "
                    "select_strategy: {available?: [str]}. "
                    "create_experiment: {hypothesis, method, variables?}. "
                    "complete_experiment: {experiment_id, result: {}, conclusion, falsified?}. "
                    "list_experiments: {status?, limit?}."
                ),
            },
            "strategy": {"type": "string", "description": "Strategy name for record_result"},
            "success": {"type": "boolean", "description": "Whether strategy was successful"},
            "fitness_gain": {"type": "number", "description": "Optional fitness gain value"},
            "available": {
                "type": "array", "items": {"type": "string"},
                "description": "Available strategies for select_strategy",
            },
            "hypothesis": {"type": "string", "description": "Hypothesis for create_experiment"},
            "method": {"type": "string", "description": "Method for create_experiment"},
            "variables": {"type": "object", "description": "Variables for create_experiment"},
            "experiment_id": {"type": "string", "description": "Experiment ID for complete_experiment"},
            "result": {"type": "object", "description": "Result dict for complete_experiment"},
            "conclusion": {"type": "string", "description": "Conclusion for complete_experiment"},
            "falsified": {"type": "boolean", "description": "Whether hypothesis was falsified"},
            "status": {"type": "string", "description": "Filter for list_experiments"},
            "limit": {"type": "integer", "description": "Limit for list_experiments"},
        },
        "required": ["action"],
    }

    def __init__(self, workspace: str | None = None) -> None:
        self._engine = MetaLearningEngine(workspace)
        self._tracker = ExperimentTracker(workspace)

    @property
    def engine(self) -> MetaLearningEngine:
        return self._engine

    @property
    def tracker(self) -> ExperimentTracker:
        return self._tracker

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        if action == "record_result":
            strategy = kwargs.get("strategy", "")
            success = kwargs.get("success")
            if not strategy or success is None:
                return json.dumps({"error": "strategy and success required"})
            result = self._engine.record_strategy_result(
                strategy, bool(success), float(kwargs.get("fitness_gain", 0.0)),
            )
            return json.dumps(result, default=str)

        if action == "select_strategy":
            available = kwargs.get("available")
            result = self._engine.select_best_strategy(available)
            return json.dumps(result)

        if action == "detect_problems":
            problems = self._engine.detect_learning_problems()
            return json.dumps({"problems": problems})

        if action == "meta_cycle":
            result = self._engine.meta_cycle()
            return json.dumps(result, default=str)

        if action == "get_status":
            return json.dumps(self._engine.get_status())

        if action == "get_rankings":
            return json.dumps(self._engine.get_strategy_rankings(), default=str)

        if action == "create_experiment":
            hypothesis = kwargs.get("hypothesis", "")
            method = kwargs.get("method", "")
            if not hypothesis or not method:
                return json.dumps({"error": "hypothesis and method required"})
            exp = self._tracker.create(hypothesis, method, kwargs.get("variables"))
            return json.dumps(exp.to_dict())

        if action == "complete_experiment":
            exp_id = kwargs.get("experiment_id", "")
            result_data = kwargs.get("result", {})
            conclusion = kwargs.get("conclusion", "")
            if not exp_id or not conclusion:
                return json.dumps({"error": "experiment_id and conclusion required"})
            exp = self._tracker.complete(
                exp_id, result_data, conclusion, kwargs.get("falsified", False),
            )
            if exp is None:
                return json.dumps({"error": f"Experiment {exp_id} not found"})
            return json.dumps(exp.to_dict())

        if action == "list_experiments":
            exps = self._tracker.list_experiments(
                kwargs.get("status"), kwargs.get("limit", 20),
            )
            return json.dumps(exps)

        if action == "experiment_summary":
            return json.dumps(self._tracker.summary())

        return json.dumps({"error": f"Unknown action: {action}"})
