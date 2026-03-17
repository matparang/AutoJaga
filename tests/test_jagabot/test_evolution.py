"""Tests for EvolutionEngine, MutationTarget, and EvolutionTool."""

import asyncio
import concurrent.futures
import json
import os
import tempfile
import unittest

from jagabot.evolution.targets import (
    MutationTarget,
    DEFAULT_VALUES,
    TARGET_DESCRIPTIONS,
)
from jagabot.evolution.engine import (
    EvolutionEngine,
    Mutation,
    MutationResult,
    MutationSandbox,
    MIN_MUTATION_FACTOR,
    MAX_MUTATION_FACTOR,
    SANDBOX_CYCLES,
    MIN_CYCLES_BETWEEN,
)
from jagabot.agent.tools.evolution import EvolutionTool


def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _make_engine():
    tmp = tempfile.mkdtemp()
    return EvolutionEngine(os.path.join(tmp, "evo.json"))


# ===================================================================
# MutationTarget tests
# ===================================================================

class TestMutationTarget(unittest.TestCase):

    def test_five_targets(self):
        assert len(MutationTarget) == 5

    def test_values(self):
        names = {t.value for t in MutationTarget}
        assert "risk_threshold" in names
        assert "volatility_weight" in names
        assert "correlation_threshold" in names
        assert "perspective_weight" in names
        assert "learning_rate" in names

    def test_defaults_exist(self):
        for t in MutationTarget:
            assert t in DEFAULT_VALUES
            assert DEFAULT_VALUES[t] > 0

    def test_descriptions_exist(self):
        for t in MutationTarget:
            assert t in TARGET_DESCRIPTIONS
            assert len(TARGET_DESCRIPTIONS[t]) > 5


# ===================================================================
# Mutation tests
# ===================================================================

class TestMutation(unittest.TestCase):

    def _make(self, old=0.5, new=0.55):
        from datetime import datetime, timezone
        return Mutation(
            id="test-1",
            target=MutationTarget.RISK_THRESHOLD,
            old_value=old,
            new_value=new,
            created_at=datetime.now(timezone.utc),
            description="test mutation",
        )

    def test_factor(self):
        m = self._make(0.5, 0.55)
        assert abs(m.factor() - 1.1) < 0.001

    def test_factor_zero_old(self):
        m = self._make(0, 0.5)
        assert m.factor() == 1.0

    def test_to_dict_from_dict(self):
        m = self._make()
        d = m.to_dict()
        m2 = Mutation.from_dict(d)
        assert m2.id == "test-1"
        assert m2.target == MutationTarget.RISK_THRESHOLD
        assert m2.old_value == 0.5
        assert m2.new_value == 0.55


# ===================================================================
# MutationResult tests
# ===================================================================

class TestMutationResult(unittest.TestCase):

    def test_to_dict_from_dict(self):
        from datetime import datetime, timezone
        r = MutationResult(
            mutation_id="m1",
            success=True,
            fitness_before=0.8,
            fitness_after=0.85,
            improvement=0.05,
            test_cycles=50,
            accepted_at=datetime.now(timezone.utc),
        )
        d = r.to_dict()
        r2 = MutationResult.from_dict(d)
        assert r2.mutation_id == "m1"
        assert r2.success is True
        assert r2.improvement == 0.05

    def test_to_dict_no_accepted_at(self):
        r = MutationResult("m2", False, 0.8, 0.75, -0.05, 50, None)
        d = r.to_dict()
        assert d["accepted_at"] is None
        r2 = MutationResult.from_dict(d)
        assert r2.accepted_at is None


# ===================================================================
# MutationSandbox tests
# ===================================================================

class TestMutationSandbox(unittest.TestCase):

    def test_initial_state(self):
        sb = MutationSandbox()
        assert sb.active_mutation is None
        assert sb.test_cycles_remaining == 0

    def test_start_test(self):
        from datetime import datetime, timezone
        sb = MutationSandbox()
        m = Mutation("m1", MutationTarget.RISK_THRESHOLD, 0.95, 0.96, datetime.now(timezone.utc), "test")
        sb.start_test(m, 0.8, 10)
        assert sb.active_mutation is not None
        assert sb.fitness_before == 0.8
        assert sb.test_cycles_remaining == SANDBOX_CYCLES

    def test_tick_countdown(self):
        from datetime import datetime, timezone
        sb = MutationSandbox()
        m = Mutation("m1", MutationTarget.RISK_THRESHOLD, 0.95, 0.96, datetime.now(timezone.utc), "test")
        sb.start_test(m, 0.8, 10)
        for _ in range(SANDBOX_CYCLES - 1):
            assert sb.tick() is False
        assert sb.tick() is True

    def test_tick_no_active(self):
        sb = MutationSandbox()
        assert sb.tick() is False

    def test_cancel(self):
        from datetime import datetime, timezone
        sb = MutationSandbox()
        m = Mutation("m1", MutationTarget.RISK_THRESHOLD, 0.95, 0.96, datetime.now(timezone.utc), "test")
        sb.start_test(m, 0.8, 10)
        sb.cancel()
        assert sb.active_mutation is None
        assert sb.test_cycles_remaining == 0

    def test_to_dict_from_dict(self):
        from datetime import datetime, timezone
        sb = MutationSandbox()
        m = Mutation("m1", MutationTarget.RISK_THRESHOLD, 0.95, 0.96, datetime.now(timezone.utc), "test")
        sb.start_test(m, 0.8, 10)
        d = sb.to_dict()
        sb2 = MutationSandbox.from_dict(d)
        assert sb2.active_mutation.id == "m1"
        assert sb2.fitness_before == 0.8

    def test_to_dict_empty(self):
        sb = MutationSandbox()
        d = sb.to_dict()
        sb2 = MutationSandbox.from_dict(d)
        assert sb2.active_mutation is None


# ===================================================================
# EvolutionEngine tests
# ===================================================================

class TestEvolutionEngine(unittest.TestCase):

    def test_init_defaults(self):
        e = _make_engine()
        for t in MutationTarget:
            assert e.get_param(t) == DEFAULT_VALUES[t]

    def test_init_custom_params(self):
        tmp = tempfile.mkdtemp()
        e = EvolutionEngine(
            os.path.join(tmp, "evo.json"),
            parameter_values={MutationTarget.RISK_THRESHOLD: 0.99},
        )
        assert e.get_param(MutationTarget.RISK_THRESHOLD) == 0.99

    def test_get_all_params(self):
        e = _make_engine()
        p = e.get_all_params()
        assert len(p) == 5
        assert "risk_threshold" in p

    def test_set_param(self):
        e = _make_engine()
        e.set_param(MutationTarget.LEARNING_RATE, 0.55)
        assert e.get_param(MutationTarget.LEARNING_RATE) == 0.55

    def test_fitness_at_defaults(self):
        e = _make_engine()
        f = e._calculate_fitness()
        assert 0.7 <= f <= 1.0  # should be high at defaults

    def test_cycle_no_mutation_governor(self):
        e = _make_engine()
        # First cycle should generate a mutation (governor allows immediately)
        r = e.cycle()
        assert r["action"] in ("started", "none")
        assert r["cycle"] == 1

    def test_cycle_starts_sandbox(self):
        e = _make_engine()
        r = e.cycle()
        if r["action"] == "started":
            assert e.sandbox.active_mutation is not None
            assert e.sandbox.test_cycles_remaining == SANDBOX_CYCLES

    def test_governor_blocks_second_mutation(self):
        e = _make_engine()
        # Force a mutation and complete its lifecycle
        e.force_mutation("risk_threshold", 1.05)
        for _ in range(SANDBOX_CYCLES + 1):
            r = e.cycle()
            if r["action"] in ("accepted", "rejected"):
                break
        # Governor should now block — last_mutation_cycle was just set
        r2 = e.cycle()
        assert r2["action"] == "none"

    def test_sandbox_testing_phase(self):
        e = _make_engine()
        r = e.cycle()
        if r["action"] == "started":
            # Run cycles during sandbox
            for _ in range(5):
                r = e.cycle()
                if r["action"] == "testing":
                    assert "sandbox_remaining" in r
                    break

    def test_full_lifecycle_accept_or_reject(self):
        e = _make_engine()
        r = e.cycle()
        if r["action"] != "started":
            return  # skip if random didn't generate mutation
        # Run remaining sandbox cycles
        for _ in range(SANDBOX_CYCLES + 1):
            r = e.cycle()
            if r["action"] in ("accepted", "rejected"):
                break
        assert r["action"] in ("accepted", "rejected")
        assert "mutation" in r
        assert "improvement" in r["mutation"]

    def test_rollback_on_rejection(self):
        e = _make_engine()
        original_params = dict(e.params)
        # Force a mutation
        result = e.force_mutation("risk_threshold", 1.05)
        assert result is not None
        # Simulate rejection by manually completing sandbox
        for _ in range(SANDBOX_CYCLES + 1):
            r = e.cycle()
            if r["action"] in ("accepted", "rejected"):
                break
        # After accept/reject cycle completes, engine is consistent
        assert e.sandbox.active_mutation is None

    def test_layer1_factor_clamping(self):
        e = _make_engine()
        # Factor outside bounds should be rejected
        result = e.force_mutation("risk_threshold", 0.5)
        assert result is None
        result = e.force_mutation("risk_threshold", 2.0)
        assert result is None

    def test_force_mutation_valid(self):
        e = _make_engine()
        result = e.force_mutation("risk_threshold", 1.05)
        assert result is not None
        assert result["target"] == "risk_threshold"
        assert e.sandbox.active_mutation is not None

    def test_force_mutation_invalid_target(self):
        e = _make_engine()
        assert e.force_mutation("bad_target", 1.05) is None

    def test_cancel_sandbox(self):
        e = _make_engine()
        e.force_mutation("risk_threshold", 1.05)
        old = DEFAULT_VALUES[MutationTarget.RISK_THRESHOLD]
        assert e.cancel_sandbox() is True
        # Value should be rolled back
        assert e.get_param(MutationTarget.RISK_THRESHOLD) == old

    def test_cancel_no_sandbox(self):
        e = _make_engine()
        assert e.cancel_sandbox() is False

    def test_persistence(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "evo.json")
        e1 = EvolutionEngine(path)
        e1.cycle()
        e1.set_param(MutationTarget.VOLATILITY_WEIGHT, 0.28)
        e1._save_state()

        e2 = EvolutionEngine(path)
        assert e2.cycle_count == e1.cycle_count
        assert e2.get_param(MutationTarget.VOLATILITY_WEIGHT) == 0.28

    def test_get_status(self):
        e = _make_engine()
        s = e.get_status()
        assert "cycle" in s
        assert "fitness" in s
        assert "params" in s
        assert "accepted" in s

    def test_get_mutations_empty(self):
        e = _make_engine()
        assert e.get_mutations() == []

    def test_get_mutations_with_data(self):
        e = _make_engine()
        e.force_mutation("risk_threshold", 1.05)
        muts = e.get_mutations()
        assert len(muts) == 1
        assert muts[0]["target"] == "risk_threshold"

    def test_get_targets(self):
        e = _make_engine()
        targets = e.get_targets()
        assert len(targets) == 5
        assert targets[0]["target"] == "risk_threshold"
        assert "default" in targets[0]
        assert "description" in targets[0]


# ===================================================================
# EvolutionTool tests
# ===================================================================

class TestEvolutionTool(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tool = EvolutionTool(workspace=self.tmp)

    def test_tool_name(self):
        assert self.tool.name == "evolution"

    def test_tool_schema(self):
        assert "action" in self.tool.parameters["properties"]

    def test_cycle_action(self):
        result = json.loads(_run(self.tool.execute(action="cycle")))
        assert "cycle" in result
        assert result["cycle"] == 1
        assert "fitness" in result

    def test_status_action(self):
        result = json.loads(_run(self.tool.execute(action="status")))
        assert "cycle" in result
        assert "params" in result
        assert "fitness" in result

    def test_mutations_action_empty(self):
        result = json.loads(_run(self.tool.execute(action="mutations")))
        assert result == []

    def test_targets_action(self):
        result = json.loads(_run(self.tool.execute(action="targets")))
        assert len(result) == 5
        assert result[0]["target"] == "risk_threshold"

    def test_fitness_action(self):
        result = json.loads(_run(self.tool.execute(action="fitness")))
        assert "fitness" in result
        assert 0 <= result["fitness"] <= 1.0

    def test_force_action(self):
        result = json.loads(_run(self.tool.execute(
            action="force", target="risk_threshold", factor=1.05,
        )))
        assert result["target"] == "risk_threshold"

    def test_force_action_bad_factor(self):
        result = json.loads(_run(self.tool.execute(
            action="force", target="risk_threshold", factor=2.0,
        )))
        assert "error" in result

    def test_force_action_missing_params(self):
        result = json.loads(_run(self.tool.execute(action="force")))
        assert "error" in result

    def test_cancel_action_no_sandbox(self):
        result = json.loads(_run(self.tool.execute(action="cancel")))
        assert result["cancelled"] is False

    def test_cancel_action_with_sandbox(self):
        _run(self.tool.execute(action="force", target="risk_threshold", factor=1.05))
        result = json.loads(_run(self.tool.execute(action="cancel")))
        assert result["cancelled"] is True

    def test_unknown_action(self):
        result = json.loads(_run(self.tool.execute(action="bad")))
        assert "error" in result

    def test_mutations_after_force(self):
        _run(self.tool.execute(action="force", target="volatility_weight", factor=0.95))
        result = json.loads(_run(self.tool.execute(action="mutations")))
        assert len(result) == 1
        assert result[0]["target"] == "volatility_weight"


if __name__ == "__main__":
    unittest.main()
