"""Tests for K1 Bayesian kernel and tool."""

import asyncio
import json
import os
import tempfile
import unittest

from jagabot.kernels.k1_bayesian import K1Bayesian, CalibrationStore
from jagabot.agent.tools.k1_bayesian import K1BayesianTool


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
# CalibrationStore tests
# ===================================================================

class TestCalibrationStore(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = CalibrationStore(self.tmp)

    def test_empty_store(self):
        assert self.store.brier_score("bull") is None
        assert self.store.count("bull") == 0
        assert self.store.get_records("bull") == []

    def test_record_and_count(self):
        self.store.record("bull", 0.8, True)
        self.store.record("bull", 0.6, False)
        assert self.store.count("bull") == 2

    def test_brier_score_perfect(self):
        self.store.record("bull", 1.0, True)
        self.store.record("bull", 0.0, False)
        assert self.store.brier_score("bull") == 0.0

    def test_brier_score_worst(self):
        self.store.record("bear", 1.0, False)
        self.store.record("bear", 0.0, True)
        assert self.store.brier_score("bear") == 1.0

    def test_brier_score_mixed(self):
        self.store.record("buffet", 0.7, True)
        # (0.7 - 1.0)^2 = 0.09
        brier = self.store.brier_score("buffet")
        assert abs(brier - 0.09) < 0.001

    def test_persistence(self):
        self.store.record("bull", 0.8, True)
        store2 = CalibrationStore(self.tmp)
        assert store2.count("bull") == 1

    def test_get_all_perspectives(self):
        self.store.record("bull", 0.8, True)
        self.store.record("bear", 0.3, False)
        assert set(self.store.get_all_perspectives()) == {"bull", "bear"}

    def test_clear_perspective(self):
        self.store.record("bull", 0.8, True)
        self.store.record("bear", 0.3, False)
        self.store.clear("bull")
        assert self.store.count("bull") == 0
        assert self.store.count("bear") == 1

    def test_clear_all(self):
        self.store.record("bull", 0.8, True)
        self.store.record("bear", 0.3, False)
        self.store.clear()
        assert self.store.get_all_perspectives() == []


# ===================================================================
# K1Bayesian kernel tests
# ===================================================================

class TestK1Bayesian(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.k1 = K1Bayesian(self.tmp)

    def test_prior_uninformative(self):
        assert self.k1.prior("anything") == 0.5

    def test_posterior_equal_priors(self):
        result = self.k1.posterior(0.5, 0.5)
        assert abs(result - 0.5) < 0.01

    def test_posterior_high_likelihood(self):
        result = self.k1.posterior(0.5, 0.9)
        assert result > 0.8

    def test_posterior_low_likelihood(self):
        result = self.k1.posterior(0.5, 0.1)
        assert result < 0.2

    def test_posterior_bounds(self):
        assert 0.0 <= self.k1.posterior(0.0, 0.5) <= 1.0
        assert 0.0 <= self.k1.posterior(1.0, 0.5) <= 1.0

    def test_update_returns_dict(self):
        result = self.k1.update("crisis", {"severity": 0.8})
        assert "posterior" in result
        assert "prior" in result
        assert "likelihood" in result
        assert result["direction"] in ("strengthened", "weakened", "unchanged")

    def test_update_history(self):
        self.k1.update("topic1", {"x": 0.7})
        self.k1.update("topic2", {"y": 0.3})
        assert len(self.k1.history) == 2

    def test_ci_returns_tuple(self):
        lo, hi = self.k1.ci(0.5, 100)
        assert lo < 0.5 < hi
        assert 0.0 <= lo <= hi <= 1.0

    def test_ci_zero_n(self):
        lo, hi = self.k1.ci(0.5, 0)
        assert lo == 0.0
        assert hi == 1.0

    def test_assess_returns_dict(self):
        result = self.k1.assess("market crash")
        assert "prior" in result
        assert "ci_lower" in result
        assert "ci_upper" in result
        assert "uncertainty" in result

    def test_likelihood_empty_data(self):
        assert self.k1.likelihood({}) == 0.5

    def test_likelihood_numeric_data(self):
        result = self.k1.likelihood({"a": 0.8, "b": 0.6})
        assert abs(result - 0.7) < 0.01


# ===================================================================
# Confidence refinement tests
# ===================================================================

class TestConfidenceRefinement(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.k1 = K1Bayesian(self.tmp)

    def test_no_history_returns_raw(self):
        result = self.k1.refine_confidence(75.0, "bull")
        assert result == 75.0

    def test_few_records_returns_raw(self):
        for _ in range(3):
            self.k1.record_outcome("bull", 0.8, True)
        result = self.k1.refine_confidence(75.0, "bull")
        assert result == 75.0  # <5 records, no adjustment

    def test_perfect_calibration_no_shrink(self):
        for _ in range(10):
            self.k1.record_outcome("bull", 1.0, True)
            self.k1.record_outcome("bull", 0.0, False)
        # Brier = 0.0 → shrinkage = 1.0 → no change
        result = self.k1.refine_confidence(80.0, "bull")
        assert abs(result - 80.0) < 0.01

    def test_poor_calibration_shrinks(self):
        for _ in range(10):
            self.k1.record_outcome("bear", 1.0, False)  # always wrong
        # Brier = 1.0 → shrinkage = max(0.5, 1 - 2) = 0.5
        result = self.k1.refine_confidence(90.0, "bear")
        # 50 + (90-50)*0.5 = 70
        assert abs(result - 70.0) < 0.01

    def test_record_outcome_returns_stats(self):
        result = self.k1.record_outcome("bull", 0.8, True)
        assert result["perspective"] == "bull"
        assert result["n_records"] == 1
        assert result["brier_score"] is not None


# ===================================================================
# Get calibration tests
# ===================================================================

class TestGetCalibration(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.k1 = K1Bayesian(self.tmp)

    def test_no_data(self):
        result = self.k1.get_calibration()
        assert "message" in result

    def test_single_perspective(self):
        for _ in range(10):
            self.k1.record_outcome("bull", 0.8, True)
        result = self.k1.get_calibration("bull")
        assert result["n_records"] == 10
        assert result["brier_score"] is not None
        assert result["quality"] in ("excellent", "good", "fair", "poor")

    def test_all_perspectives(self):
        self.k1.record_outcome("bull", 0.8, True)
        self.k1.record_outcome("bear", 0.3, False)
        result = self.k1.get_calibration()
        assert "bull" in result
        assert "bear" in result


# ===================================================================
# K1BayesianTool tests
# ===================================================================

class TestK1BayesianTool(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tool = K1BayesianTool(workspace=self.tmp)

    def test_tool_name(self):
        assert self.tool.name == "k1_bayesian"

    def test_tool_schema(self):
        assert "action" in self.tool.parameters["properties"]

    def test_update_belief_action(self):
        result = json.loads(_run(self.tool.execute(
            action="update_belief", topic="crisis", evidence={"severity": 0.8}
        )))
        assert "posterior" in result

    def test_update_belief_requires_topic(self):
        result = json.loads(_run(self.tool.execute(action="update_belief")))
        assert "error" in result

    def test_assess_action(self):
        result = json.loads(_run(self.tool.execute(
            action="assess", problem="market crash"
        )))
        assert "uncertainty" in result

    def test_refine_confidence_action(self):
        result = json.loads(_run(self.tool.execute(
            action="refine_confidence", raw_confidence=75.0, perspective="bull"
        )))
        assert result["refined"] == 75.0  # no history yet

    def test_record_outcome_action(self):
        result = json.loads(_run(self.tool.execute(
            action="record_outcome", perspective="bull",
            predicted_prob=0.8, actual=True
        )))
        assert result["n_records"] == 1

    def test_get_calibration_action(self):
        _run(self.tool.execute(
            action="record_outcome", perspective="bull",
            predicted_prob=0.8, actual=True
        ))
        result = json.loads(_run(self.tool.execute(
            action="get_calibration", perspective="bull"
        )))
        assert result["n_records"] == 1

    def test_unknown_action(self):
        result = json.loads(_run(self.tool.execute(action="bad")))
        assert "error" in result


if __name__ == "__main__":
    unittest.main()
