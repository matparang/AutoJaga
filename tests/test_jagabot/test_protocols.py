"""Tests for jagabot.swarm.protocols — FSM shutdown & plan approval protocols."""
import threading
import time
from pathlib import Path

import pytest

from jagabot.swarm.mailbox import Mailbox
from jagabot.swarm.protocols import ShutdownProtocol, PlanApprovalProtocol


@pytest.fixture
def mb(tmp_path):
    return Mailbox(tmp_path / "inboxes")


@pytest.fixture
def shutdown(mb):
    return ShutdownProtocol(mb)


@pytest.fixture
def plan_proto(mb):
    return PlanApprovalProtocol(mb)


# ── ShutdownProtocol ─────────────────────────────────────────────────

class TestShutdownProtocol:
    def test_request_returns_id(self, shutdown):
        rid = shutdown.request_shutdown("boss", "alice")
        assert isinstance(rid, str)
        assert len(rid) == 12

    def test_request_status_pending(self, shutdown):
        rid = shutdown.request_shutdown("boss", "alice")
        assert shutdown.check_shutdown(rid) == "pending"

    def test_respond_approve(self, shutdown):
        rid = shutdown.request_shutdown("boss", "alice")
        shutdown.respond_shutdown(rid, approve=True)
        assert shutdown.check_shutdown(rid) == "approved"

    def test_respond_reject(self, shutdown):
        rid = shutdown.request_shutdown("boss", "alice")
        shutdown.respond_shutdown(rid, approve=False)
        assert shutdown.check_shutdown(rid) == "rejected"

    def test_respond_unknown_id(self, shutdown):
        with pytest.raises(ValueError, match="Unknown request_id"):
            shutdown.respond_shutdown("nonexistent", approve=True)

    def test_check_unknown_id(self, shutdown):
        assert shutdown.check_shutdown("nonexistent") == "unknown"

    def test_sends_mailbox_message(self, shutdown, mb):
        shutdown.request_shutdown("boss", "alice")
        msgs = mb.read_inbox("alice")
        assert len(msgs) == 1
        assert msgs[0]["type"] == "shutdown_request"

    def test_list_requests(self, shutdown):
        shutdown.request_shutdown("boss", "alice")
        shutdown.request_shutdown("boss", "bob")
        reqs = shutdown.list_requests()
        assert len(reqs) == 2

    def test_list_requests_empty(self, shutdown):
        assert shutdown.list_requests() == []

    def test_concurrent_requests(self, shutdown):
        ids = []
        def make_request():
            rid = shutdown.request_shutdown("boss", "worker")
            ids.append(rid)

        threads = [threading.Thread(target=make_request) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(ids) == 10
        assert len(set(ids)) == 10  # all unique

    def test_request_has_metadata(self, shutdown, mb):
        rid = shutdown.request_shutdown("boss", "alice")
        msgs = mb.read_inbox("alice")
        assert msgs[0]["meta"]["request_id"] == rid


# ── PlanApprovalProtocol ─────────────────────────────────────────────

class TestPlanApprovalProtocol:
    def test_submit_returns_id(self, plan_proto):
        pid = plan_proto.submit_plan("alice", ["bob"], "Build API")
        assert isinstance(pid, str)
        assert len(pid) == 12

    def test_submit_status_pending(self, plan_proto):
        pid = plan_proto.submit_plan("alice", ["bob"], "Build API")
        result = plan_proto.check_plan(pid)
        assert result["status"] == "pending"

    def test_submit_sends_to_reviewers(self, plan_proto, mb):
        plan_proto.submit_plan("alice", ["bob", "charlie"], "Plan X")
        assert len(mb.read_inbox("bob")) == 1
        assert len(mb.read_inbox("charlie")) == 1

    def test_review_approve(self, plan_proto):
        pid = plan_proto.submit_plan("alice", ["bob"], "Plan X")
        plan_proto.review_plan(pid, "bob", approve=True)
        result = plan_proto.check_plan(pid)
        assert result["status"] == "approved"

    def test_review_reject(self, plan_proto):
        pid = plan_proto.submit_plan("alice", ["bob"], "Plan X")
        plan_proto.review_plan(pid, "bob", approve=False, feedback="needs work")
        result = plan_proto.check_plan(pid)
        assert result["status"] == "rejected"

    def test_partial_review(self, plan_proto):
        pid = plan_proto.submit_plan("alice", ["bob", "charlie"], "Plan X")
        plan_proto.review_plan(pid, "bob", approve=True)
        result = plan_proto.check_plan(pid)
        assert result["status"] == "pending"
        assert "charlie" in result["pending_reviewers"]

    def test_all_approve(self, plan_proto):
        pid = plan_proto.submit_plan("alice", ["bob", "charlie"], "Plan X")
        plan_proto.review_plan(pid, "bob", approve=True)
        plan_proto.review_plan(pid, "charlie", approve=True)
        result = plan_proto.check_plan(pid)
        assert result["status"] == "approved"

    def test_mixed_reviews_reject(self, plan_proto):
        pid = plan_proto.submit_plan("alice", ["bob", "charlie"], "Plan X")
        plan_proto.review_plan(pid, "bob", approve=True)
        plan_proto.review_plan(pid, "charlie", approve=False)
        result = plan_proto.check_plan(pid)
        assert result["status"] == "rejected"

    def test_review_unknown_plan(self, plan_proto):
        with pytest.raises(ValueError, match="Unknown plan_id"):
            plan_proto.review_plan("nonexistent", "bob", approve=True)

    def test_check_unknown_plan(self, plan_proto):
        result = plan_proto.check_plan("nonexistent")
        assert result["status"] == "unknown"

    def test_review_with_feedback(self, plan_proto):
        pid = plan_proto.submit_plan("alice", ["bob"], "Plan X")
        plan_proto.review_plan(pid, "bob", approve=True, feedback="LGTM")
        result = plan_proto.check_plan(pid)
        assert result["reviews"]["bob"]["feedback"] == "LGTM"

    def test_list_plans(self, plan_proto):
        plan_proto.submit_plan("alice", ["bob"], "Plan A")
        plan_proto.submit_plan("alice", ["bob"], "Plan B")
        plans = plan_proto.list_plans()
        assert len(plans) == 2

    def test_list_plans_empty(self, plan_proto):
        assert plan_proto.list_plans() == []

    def test_plan_message_has_plan_id(self, plan_proto, mb):
        pid = plan_proto.submit_plan("alice", ["bob"], "Plan X")
        msgs = mb.read_inbox("bob")
        assert msgs[0]["meta"]["plan_id"] == pid

    def test_plan_message_type(self, plan_proto, mb):
        plan_proto.submit_plan("alice", ["bob"], "Plan X")
        msgs = mb.read_inbox("bob")
        assert msgs[0]["type"] == "plan_approval"

    def test_concurrent_reviews(self, plan_proto):
        pid = plan_proto.submit_plan("alice", [f"r{i}" for i in range(10)], "Plan X")
        threads = []
        for i in range(10):
            t = threading.Thread(
                target=plan_proto.review_plan,
                args=(pid, f"r{i}", True),
            )
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        result = plan_proto.check_plan(pid)
        assert result["status"] == "approved"
        assert len(result["reviews"]) == 10

    def test_submit_with_description(self, plan_proto, mb):
        plan_proto.submit_plan("alice", ["bob"], "Plan X", description="Build REST API")
        msgs = mb.read_inbox("bob")
        assert msgs[0]["meta"]["description"] == "Build REST API"
