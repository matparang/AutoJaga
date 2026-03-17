"""Tests for MetaLearningEngine, ExperimentTracker, and MetaLearningTool."""

import asyncio
import json
import tempfile
import unittest

from jagabot.engines.meta_learning import (
    MetaLearningEngine, StrategyStats, MetaMetrics,
    KNOWN_STRATEGIES, META_CYCLE_INTERVAL, MIN_SAMPLES_FOR_STRATEGY,
)
from jagabot.engines.experiment_tracker import ExperimentTracker, Experiment
from jagabot.agent.tools.meta_learning import MetaLearningTool


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


# ===================================================================
# StrategyStats tests
# ===================================================================

class TestStrategyStats(unittest.TestCase):

    def test_initial_state(self):
        s = StrategyStats(name="bull_analysis")
        assert s.attempts == 0
        assert s.success_rate() == 0.0
        assert s.avg_fitness_gain() == 0.0
        assert s.confidence() == 0.0
        assert s.score() == 0.0

    def test_success_rate(self):
        s = StrategyStats(name="test", attempts=10, successes=7)
        assert abs(s.success_rate() - 0.7) < 0.01

    def test_avg_fitness_gain(self):
        s = StrategyStats(name="test", attempts=4, total_fitness_gain=0.2)
        assert abs(s.avg_fitness_gain() - 0.05) < 0.001

    def test_confidence_grows(self):
        s = StrategyStats(name="test", attempts=3)
        assert s.confidence() < 1.0
        s.attempts = MIN_SAMPLES_FOR_STRATEGY
        assert s.confidence() == 1.0

    def test_score_weighted_by_confidence(self):
        s = StrategyStats(name="test", attempts=1, successes=1)
        low_conf_score = s.score()
        s.attempts = MIN_SAMPLES_FOR_STRATEGY
        s.successes = MIN_SAMPLES_FOR_STRATEGY
        high_conf_score = s.score()
        assert high_conf_score > low_conf_score

    def test_to_dict_from_dict(self):
        s = StrategyStats(name="bull_analysis", attempts=5, successes=3, total_fitness_gain=0.1)
        d = s.to_dict()
        s2 = StrategyStats.from_dict(d)
        assert s2.name == "bull_analysis"
        assert s2.attempts == 5
        assert s2.successes == 3


# ===================================================================
# MetaLearningEngine tests
# ===================================================================

class TestMetaLearningEngine(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.engine = MetaLearningEngine(self.tmp)

    def test_init_strategies(self):
        assert len(self.engine.strategies) == len(KNOWN_STRATEGIES)
        for name in KNOWN_STRATEGIES:
            assert name in self.engine.strategies

    def test_record_strategy_result(self):
        result = self.engine.record_strategy_result("bull_analysis", True, 0.05)
        assert result["strategy"] == "bull_analysis"
        assert result["success"] is True
        assert result["total_records"] == 1
        assert self.engine.strategies["bull_analysis"].attempts == 1
        assert self.engine.strategies["bull_analysis"].successes == 1

    def test_record_failure(self):
        self.engine.record_strategy_result("bear_analysis", False, -0.02)
        s = self.engine.strategies["bear_analysis"]
        assert s.attempts == 1
        assert s.successes == 0

    def test_record_unknown_strategy(self):
        result = self.engine.record_strategy_result("new_strategy", True)
        assert result["strategy"] == "new_strategy"
        assert "new_strategy" in self.engine.strategies

    def test_persistence(self):
        self.engine.record_strategy_result("bull_analysis", True, 0.1)
        engine2 = MetaLearningEngine(self.tmp)
        assert engine2.strategies["bull_analysis"].attempts == 1
        assert engine2.total_records == 1

    def test_select_best_strategy_exploration(self):
        result = self.engine.select_best_strategy()
        assert result["reason"] == "exploration"
        assert result["strategy"] in KNOWN_STRATEGIES

    def test_select_best_strategy_exploitation(self):
        for _ in range(MIN_SAMPLES_FOR_STRATEGY + 1):
            self.engine.record_strategy_result("bull_analysis", True, 0.1)
            self.engine.record_strategy_result("bear_analysis", False)
        result = self.engine.select_best_strategy(["bull_analysis", "bear_analysis"])
        assert result["strategy"] == "bull_analysis"
        assert result["reason"] == "exploitation"

    def test_detect_problems_clean(self):
        for _ in range(MIN_SAMPLES_FOR_STRATEGY):
            self.engine.record_strategy_result("bull_analysis", True)
        problems = self.engine.detect_learning_problems()
        assert "low_strategy_success" not in problems

    def test_detect_low_strategy_success(self):
        for name in KNOWN_STRATEGIES:
            for _ in range(MIN_SAMPLES_FOR_STRATEGY):
                self.engine.record_strategy_result(name, False)
        problems = self.engine.detect_learning_problems()
        assert "low_strategy_success" in problems

    def test_detect_strategy_imbalance(self):
        for name in KNOWN_STRATEGIES[:7]:
            for _ in range(MIN_SAMPLES_FOR_STRATEGY):
                self.engine.record_strategy_result(name, False)
        for name in KNOWN_STRATEGIES[7:]:
            for _ in range(MIN_SAMPLES_FOR_STRATEGY):
                self.engine.record_strategy_result(name, True)
        problems = self.engine.detect_learning_problems()
        assert "strategy_imbalance" in problems

    def test_apply_meta_fix_low_success(self):
        for _ in range(MIN_SAMPLES_FOR_STRATEGY):
            self.engine.record_strategy_result("bear_analysis", False)
        applied = self.engine.apply_meta_fix("low_strategy_success")
        assert applied is True
        assert self.engine.strategies["bear_analysis"].attempts == 0

    def test_apply_meta_fix_imbalance(self):
        for _ in range(MIN_SAMPLES_FOR_STRATEGY):
            self.engine.record_strategy_result("bear_analysis", False)
        applied = self.engine.apply_meta_fix("strategy_imbalance")
        assert applied is True
        assert self.engine.strategies["bear_analysis"].attempts == 0

    def test_meta_cycle(self):
        result = self.engine.meta_cycle()
        assert "cycle" in result
        assert result["cycle"] == 1
        assert "problems_detected" in result
        assert "fixes_applied" in result

    def test_meta_cycle_auto_trigger(self):
        for i in range(META_CYCLE_INTERVAL):
            result = self.engine.record_strategy_result("bull_analysis", True, 0.01)
        assert result["meta_cycle_triggered"] is True
        assert result["meta_cycle_result"] is not None

    def test_get_status(self):
        self.engine.record_strategy_result("bull_analysis", True)
        status = self.engine.get_status()
        assert status["total_records"] == 1
        assert status["strategies_with_data"] == 1

    def test_get_strategy_rankings(self):
        self.engine.record_strategy_result("bull_analysis", True, 0.1)
        self.engine.record_strategy_result("bear_analysis", False)
        rankings = self.engine.get_strategy_rankings()
        assert len(rankings) > 0
        assert rankings[0]["score"] >= rankings[-1]["score"]


# ===================================================================
# ExperimentTracker tests
# ===================================================================

class TestExperimentTracker(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tracker = ExperimentTracker(self.tmp)

    def test_create_experiment(self):
        exp = self.tracker.create("Bull is better in low VIX", "compare_accuracy", {"vix_range": "10-20"})
        assert exp.status == "planned"
        assert exp.hypothesis == "Bull is better in low VIX"
        assert exp.experiment_id.startswith("exp-")

    def test_start_experiment(self):
        exp = self.tracker.create("Test hypothesis", "method_a")
        started = self.tracker.start(exp.experiment_id)
        assert started.status == "running"

    def test_complete_experiment(self):
        exp = self.tracker.create("Test hypothesis", "method_a")
        self.tracker.start(exp.experiment_id)
        completed = self.tracker.complete(
            exp.experiment_id, {"accuracy": 0.85}, "Hypothesis supported", False,
        )
        assert completed.status == "completed"
        assert completed.result == {"accuracy": 0.85}
        assert completed.falsified is False

    def test_review_experiment(self):
        exp = self.tracker.create("H1", "M1")
        self.tracker.complete(exp.experiment_id, {}, "Done")
        reviewed = self.tracker.review(exp.experiment_id)
        assert reviewed.status == "reviewed"

    def test_falsified_experiment(self):
        exp = self.tracker.create("Wrong hypothesis", "method_b")
        completed = self.tracker.complete(
            exp.experiment_id, {"accuracy": 0.3}, "Hypothesis falsified", True,
        )
        assert completed.falsified is True

    def test_list_experiments(self):
        self.tracker.create("H1", "M1")
        self.tracker.create("H2", "M2")
        exps = self.tracker.list_experiments()
        assert len(exps) == 2

    def test_list_by_status(self):
        exp1 = self.tracker.create("H1", "M1")
        self.tracker.create("H2", "M2")
        self.tracker.start(exp1.experiment_id)
        assert len(self.tracker.list_experiments("running")) == 1
        assert len(self.tracker.list_experiments("planned")) == 1

    def test_get_experiment(self):
        exp = self.tracker.create("H1", "M1")
        result = self.tracker.get(exp.experiment_id)
        assert result["hypothesis"] == "H1"

    def test_get_nonexistent(self):
        assert self.tracker.get("bad-id") is None

    def test_summary(self):
        exp = self.tracker.create("H1", "M1")
        self.tracker.complete(exp.experiment_id, {}, "Done", False)
        exp2 = self.tracker.create("H2", "M2")
        self.tracker.complete(exp2.experiment_id, {}, "Nope", True)
        s = self.tracker.summary()
        assert s["total"] == 2
        assert s["completed"] == 2
        assert s["falsified"] == 1
        assert s["supported"] == 1

    def test_persistence(self):
        self.tracker.create("H1", "M1")
        tracker2 = ExperimentTracker(self.tmp)
        assert len(tracker2.list_experiments()) == 1

    def test_to_dict_from_dict(self):
        exp = Experiment(
            experiment_id="exp-1234-120000",
            hypothesis="Test",
            method="compare",
            variables={"x": 1},
        )
        d = exp.to_dict()
        exp2 = Experiment.from_dict(d)
        assert exp2.experiment_id == "exp-1234-120000"
        assert exp2.variables == {"x": 1}


# ===================================================================
# MetaLearningTool tests
# ===================================================================

class TestMetaLearningTool(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tool = MetaLearningTool(workspace=self.tmp)

    def test_tool_name(self):
        assert self.tool.name == "meta_learning"

    def test_tool_schema(self):
        assert "action" in self.tool.parameters["properties"]

    def test_record_result_action(self):
        result = json.loads(_run(self.tool.execute(
            action="record_result", strategy="bull_analysis", success=True, fitness_gain=0.05,
        )))
        assert result["strategy"] == "bull_analysis"
        assert result["total_records"] == 1

    def test_record_result_requires_params(self):
        result = json.loads(_run(self.tool.execute(action="record_result")))
        assert "error" in result

    def test_select_strategy_action(self):
        result = json.loads(_run(self.tool.execute(action="select_strategy")))
        assert "strategy" in result
        assert "reason" in result

    def test_detect_problems_action(self):
        result = json.loads(_run(self.tool.execute(action="detect_problems")))
        assert "problems" in result

    def test_meta_cycle_action(self):
        result = json.loads(_run(self.tool.execute(action="meta_cycle")))
        assert "cycle" in result
        assert result["cycle"] == 1

    def test_get_status_action(self):
        result = json.loads(_run(self.tool.execute(action="get_status")))
        assert "total_records" in result
        assert "strategies_tracked" in result

    def test_get_rankings_action(self):
        _run(self.tool.execute(
            action="record_result", strategy="bull_analysis", success=True,
        ))
        result = json.loads(_run(self.tool.execute(action="get_rankings")))
        assert isinstance(result, list)
        assert len(result) > 0

    def test_create_experiment_action(self):
        result = json.loads(_run(self.tool.execute(
            action="create_experiment",
            hypothesis="Bull outperforms in low vol",
            method="backtest",
            variables={"vol_threshold": 0.15},
        )))
        assert result["status"] == "planned"
        assert result["hypothesis"] == "Bull outperforms in low vol"

    def test_create_experiment_requires_params(self):
        result = json.loads(_run(self.tool.execute(action="create_experiment")))
        assert "error" in result

    def test_complete_experiment_action(self):
        created = json.loads(_run(self.tool.execute(
            action="create_experiment", hypothesis="H1", method="M1",
        )))
        exp_id = created["experiment_id"]
        result = json.loads(_run(self.tool.execute(
            action="complete_experiment",
            experiment_id=exp_id,
            result={"accuracy": 0.9},
            conclusion="Hypothesis supported",
        )))
        assert result["status"] == "completed"

    def test_complete_experiment_not_found(self):
        result = json.loads(_run(self.tool.execute(
            action="complete_experiment",
            experiment_id="bad-id",
            conclusion="Done",
        )))
        assert "error" in result

    def test_list_experiments_action(self):
        _run(self.tool.execute(
            action="create_experiment", hypothesis="H1", method="M1",
        ))
        result = json.loads(_run(self.tool.execute(action="list_experiments")))
        assert len(result) == 1

    def test_experiment_summary_action(self):
        result = json.loads(_run(self.tool.execute(action="experiment_summary")))
        assert "total" in result

    def test_unknown_action(self):
        result = json.loads(_run(self.tool.execute(action="bad")))
        assert "error" in result


if __name__ == "__main__":
    unittest.main()
