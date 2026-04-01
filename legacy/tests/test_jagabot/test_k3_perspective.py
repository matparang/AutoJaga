"""Tests for K3 Multi-Perspective kernel and tool."""

import asyncio
import json
import tempfile
import unittest

from jagabot.kernels.k1_bayesian import K1Bayesian
from jagabot.kernels.k3_perspective import K3MultiPerspective, AccuracyTracker
from jagabot.agent.tools.k3_perspective import K3PerspectiveTool


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


SAMPLE_DATA = {
    "probability_below_target": 30.0,
    "current_price": 150.0,
    "target_price": 120.0,
}


# ===================================================================
# AccuracyTracker tests
# ===================================================================

class TestAccuracyTracker(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tracker = AccuracyTracker(self.tmp)

    def test_empty_tracker(self):
        assert self.tracker.accuracy("bull") is None
        assert self.tracker.count("bull") == 0

    def test_record_and_count(self):
        self.tracker.record("bull", True)
        self.tracker.record("bull", False)
        assert self.tracker.count("bull") == 2

    def test_accuracy(self):
        self.tracker.record("bull", True)
        self.tracker.record("bull", True)
        self.tracker.record("bull", False)
        assert abs(self.tracker.accuracy("bull") - 2/3) < 0.01

    def test_recent_accuracy(self):
        for _ in range(15):
            self.tracker.record("bear", True)
        for _ in range(5):
            self.tracker.record("bear", False)
        recent = self.tracker.recent_accuracy("bear")
        assert recent is not None
        assert 0.0 <= recent <= 1.0

    def test_persistence(self):
        self.tracker.record("bull", True)
        tracker2 = AccuracyTracker(self.tmp)
        assert tracker2.count("bull") == 1

    def test_get_stats(self):
        self.tracker.record("bull", True)
        stats = self.tracker.get_stats("bull")
        assert stats["total"] == 1
        assert stats["correct"] == 1
        assert stats["accuracy"] == 1.0

    def test_get_stats_empty(self):
        stats = self.tracker.get_stats("bull")
        assert stats["total"] == 0
        assert stats["accuracy"] is None

    def test_clear(self):
        self.tracker.record("bull", True)
        self.tracker.clear("bull")
        assert self.tracker.count("bull") == 0

    def test_window_limit(self):
        for i in range(30):
            self.tracker.record("bull", True)
        stats = self.tracker.get_stats("bull")
        assert stats["recent_window"] == 20


# ===================================================================
# K3MultiPerspective kernel tests
# ===================================================================

class TestK3MultiPerspective(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.k1 = K1Bayesian(self.tmp)
        self.k3 = K3MultiPerspective(k1=self.k1, workspace=self.tmp)

    def test_get_perspective_bull(self):
        result = self.k3.get_perspective("bull", SAMPLE_DATA)
        assert result["perspective"] == "bull"
        assert "verdict" in result
        assert "confidence" in result
        assert "raw_confidence" in result

    def test_get_perspective_bear(self):
        result = self.k3.get_perspective("bear", SAMPLE_DATA)
        assert result["perspective"] == "bear"

    def test_get_perspective_buffet(self):
        result = self.k3.get_perspective("buffet", SAMPLE_DATA)
        assert result["perspective"] == "buffet"

    def test_get_perspective_unknown(self):
        result = self.k3.get_perspective("oracle", {})
        assert "error" in result

    def test_calibrated_field_false_initially(self):
        result = self.k3.get_perspective("bull", SAMPLE_DATA)
        assert result["calibrated"] is False  # no history yet

    def test_update_accuracy(self):
        result = self.k3.update_accuracy("bull", "BUY", "up")
        assert result["was_correct"] is True
        assert result["total"] == 1

    def test_update_accuracy_wrong(self):
        result = self.k3.update_accuracy("bull", "BUY", "down")
        assert result["was_correct"] is False

    def test_get_weights_default(self):
        result = self.k3.get_weights()
        assert result["calibrated"] is False
        assert result["weights"]["bull"] == 0.20
        assert result["weights"]["bear"] == 0.45
        assert result["weights"]["buffet"] == 0.35

    def test_get_weights_after_enough_data(self):
        for _ in range(5):
            self.k3.update_accuracy("bull", "BUY", "up")
            self.k3.update_accuracy("bear", "SELL", "down")
        # 10 total → calibrated
        result = self.k3.get_weights()
        assert result["calibrated"] is True

    def test_recalibrate_weights_sum_to_one(self):
        for _ in range(5):
            self.k3.update_accuracy("bull", "BUY", "up")
            self.k3.update_accuracy("bear", "SELL", "down")
            self.k3.update_accuracy("buffet", "BUY — Margin of Safety", "up")
        weights = self.k3.recalibrate_weights()
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_recalibrate_no_data_uses_defaults(self):
        weights = self.k3.recalibrate_weights()
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01

    def test_calibrated_collapse(self):
        result = self.k3.calibrated_collapse(SAMPLE_DATA)
        assert "final_verdict" in result
        assert "consensus" in result
        assert "weighted_score" in result

    def test_calibrated_collapse_with_extras(self):
        data = {**SAMPLE_DATA, "var_pct": 15.0, "intrinsic_value": 200.0}
        result = self.k3.calibrated_collapse(data)
        assert "final_verdict" in result

    def test_accuracy_stats_empty(self):
        result = self.k3.get_accuracy_stats()
        assert "message" in result

    def test_accuracy_stats_with_data(self):
        self.k3.update_accuracy("bull", "BUY", "up")
        result = self.k3.get_accuracy_stats()
        assert "bull" in result


# ===================================================================
# K3PerspectiveTool tests
# ===================================================================

class TestK3PerspectiveTool(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tool = K3PerspectiveTool(workspace=self.tmp)

    def test_tool_name(self):
        assert self.tool.name == "k3_perspective"

    def test_tool_schema(self):
        assert "action" in self.tool.parameters["properties"]

    def test_get_perspective_action(self):
        result = json.loads(_run(self.tool.execute(
            action="get_perspective", ptype="bull", data=SAMPLE_DATA
        )))
        assert result["perspective"] == "bull"

    def test_get_perspective_requires_ptype(self):
        result = json.loads(_run(self.tool.execute(action="get_perspective")))
        assert "error" in result

    def test_update_accuracy_action(self):
        result = json.loads(_run(self.tool.execute(
            action="update_accuracy", perspective="bull",
            predicted_verdict="BUY", actual_outcome="up"
        )))
        assert result["was_correct"] is True

    def test_get_weights_action(self):
        result = json.loads(_run(self.tool.execute(action="get_weights")))
        assert "weights" in result

    def test_recalibrate_action(self):
        result = json.loads(_run(self.tool.execute(action="recalibrate")))
        assert "weights" in result

    def test_calibrated_decision_action(self):
        result = json.loads(_run(self.tool.execute(
            action="calibrated_decision", data=SAMPLE_DATA
        )))
        assert "final_verdict" in result

    def test_accuracy_stats_action(self):
        result = json.loads(_run(self.tool.execute(action="accuracy_stats")))
        assert isinstance(result, dict)

    def test_unknown_action(self):
        result = json.loads(_run(self.tool.execute(action="bad")))
        assert "error" in result


if __name__ == "__main__":
    unittest.main()
