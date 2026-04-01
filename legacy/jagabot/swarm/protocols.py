"""FSM protocols for shutdown and plan approval.

Adapted from learn-claude-code s10.  Each protocol is a mini state-machine:
request → pending → approved / rejected.

Thread-safe: all state mutations are protected by a threading.Lock().
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Optional

from jagabot.swarm.mailbox import Mailbox


class ShutdownProtocol:
    """Request → ack/nak flow for graceful teammate shutdown."""

    def __init__(self, mailbox: Mailbox) -> None:
        self.mailbox = mailbox
        self._requests: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def request_shutdown(self, sender: str, teammate: str) -> str:
        """Send a shutdown request to *teammate*.  Returns request_id."""
        request_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._requests[request_id] = {
                "sender": sender,
                "teammate": teammate,
                "status": "pending",
                "created_at": time.time(),
            }
        self.mailbox.send(
            sender=sender,
            to=teammate,
            content="shutdown_request",
            msg_type="shutdown_request",
            meta={"request_id": request_id},
        )
        return request_id

    def respond_shutdown(self, request_id: str, approve: bool) -> None:
        """Record a shutdown response (approve / reject)."""
        with self._lock:
            if request_id not in self._requests:
                raise ValueError(f"Unknown request_id: {request_id}")
            self._requests[request_id]["status"] = "approved" if approve else "rejected"
            self._requests[request_id]["responded_at"] = time.time()

    def check_shutdown(self, request_id: str) -> str:
        """Return the current status of a shutdown request."""
        with self._lock:
            if request_id not in self._requests:
                return "unknown"
            return self._requests[request_id]["status"]

    def list_requests(self) -> list[dict[str, Any]]:
        """Return all shutdown requests."""
        with self._lock:
            return list(self._requests.values())


class PlanApprovalProtocol:
    """Submit → review → approve/reject flow for collaborative plan review."""

    def __init__(self, mailbox: Mailbox) -> None:
        self.mailbox = mailbox
        self._plans: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def submit_plan(
        self,
        submitter: str,
        reviewers: list[str],
        plan: str,
        description: str = "",
    ) -> str:
        """Submit a plan for review.  Returns plan_id."""
        plan_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._plans[plan_id] = {
                "submitter": submitter,
                "description": description,
                "plan": plan,
                "reviewers": list(reviewers),
                "reviews": {},
                "status": "pending",
                "created_at": time.time(),
            }
        for reviewer in reviewers:
            self.mailbox.send(
                sender=submitter,
                to=reviewer,
                content=plan,
                msg_type="plan_approval",
                meta={"plan_id": plan_id, "description": description},
            )
        return plan_id

    def review_plan(
        self,
        plan_id: str,
        reviewer: str,
        approve: bool,
        feedback: str = "",
    ) -> None:
        """Record a review for *plan_id*."""
        with self._lock:
            if plan_id not in self._plans:
                raise ValueError(f"Unknown plan_id: {plan_id}")
            entry = self._plans[plan_id]
            entry["reviews"][reviewer] = {
                "approve": approve,
                "feedback": feedback,
                "reviewed_at": time.time(),
            }
            # Resolve status when all reviewers have responded
            if set(entry["reviews"].keys()) == set(entry["reviewers"]):
                if all(r["approve"] for r in entry["reviews"].values()):
                    entry["status"] = "approved"
                else:
                    entry["status"] = "rejected"

    def check_plan(self, plan_id: str) -> dict[str, Any]:
        """Return plan status and reviews."""
        with self._lock:
            if plan_id not in self._plans:
                return {"status": "unknown"}
            entry = self._plans[plan_id]
            return {
                "plan_id": plan_id,
                "status": entry["status"],
                "submitter": entry["submitter"],
                "reviews": entry["reviews"],
                "pending_reviewers": [
                    r for r in entry["reviewers"] if r not in entry["reviews"]
                ],
            }

    def list_plans(self) -> list[dict[str, Any]]:
        """Return all plan entries."""
        with self._lock:
            return [
                {**v, "plan_id": k} for k, v in self._plans.items()
            ]
