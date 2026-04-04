"""
jagashell_contract.py — Intent/Result Schema for AutoJagaMAS
=============================================================
Defines the JagaShellIntent and JagaShellResult dataclasses that represent
structured intent and result messages flowing between AutoJagaMAS swarm nodes
and external consumers (dashboards, APIs, NemoClaw reasoning engine).

These are the "contracts" that make the swarm's outputs machine-readable.
Instead of passing raw text between agents, we pass structured JagaShellIntent
and JagaShellResult objects — so any downstream system can parse and act on them.

NemoClaw integration
---------------------
# TODO: wire to NemoClaw when v0.3 stable
NemoClaw v0.3 will consume JagaShellResult via a reasoning pipeline.
The schema is deliberately NemoClaw-compatible: intent_type maps to
NemoClaw TaskType, confidence maps to NemoClaw certainty_score.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Intent dataclass — represents a task sent INTO the swarm
# ---------------------------------------------------------------------------

@dataclass
class JagaShellIntent:
    """
    Represents a structured intent sent to the AutoJagaMAS swarm.

    Fields
    ------
    intent_id:
        Unique identifier for this intent (auto-generated UUID if not supplied).
    intent_type:
        Category of intent: "research", "synthesis", "verification",
        "websearch", "analysis", or "maintenance".
    query:
        The natural language query or task description.
    source_node:
        Name of the node or agent that generated this intent.
    target_node:
        Name of the node or agent that should handle this intent.
        Use "*" to broadcast to all eligible nodes.
    profile:
        AutoJaga dispatch profile hint: "RESEARCH", "SIMPLE", "CALIBRATION", etc.
        The receiving agent's BDI engine may override this.
    confidence:
        Requester's confidence in the intent correctness (0.0–1.0).
    metadata:
        Arbitrary key-value metadata (must be JSON-serialisable).
    created_at:
        ISO 8601 timestamp of intent creation (UTC).
    """

    query: str
    intent_type: str = "research"
    source_node: str = "external"
    target_node: str = "*"
    profile: str = "RESEARCH"
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    intent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_json(self) -> str:
        """Serialise to JSON string."""
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> JagaShellIntent:
        """Deserialise from JSON string."""
        data = json.loads(json_str)
        return cls(**data)

    def to_dict(self) -> dict:
        """Return as JSON-safe dict."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Result dataclass — represents a result returned FROM the swarm
# ---------------------------------------------------------------------------

@dataclass
class JagaShellResult:
    """
    Represents a structured result produced by the AutoJagaMAS swarm.

    Fields
    ------
    result_id:
        Unique identifier for this result (auto-generated UUID if not supplied).
    intent_id:
        ID of the JagaShellIntent this result answers (for correlation).
    output:
        Primary natural language output from the agent or swarm.
    producing_node:
        Name of the agent/node that produced this result.
    complexity:
        CognitiveStack complexity classification: "simple", "complex", or "critical".
    confidence:
        Agent's confidence in the output (0.0–1.0).
    model1_calls:
        Number of calls made to Model 1 (fast/local tier).
    model2_calls:
        Number of calls made to Model 2 (cloud/reasoning tier).
    escalated:
        True if the query was escalated from Model 1 to Model 2.
    elapsed_ms:
        Total wall-clock time in milliseconds for this result.
    bdi_metadata:
        Full BDI state dict from CognitiveStack (profile, engines, etc.).
    metadata:
        Arbitrary key-value metadata (must be JSON-serialisable).
    created_at:
        ISO 8601 timestamp of result creation (UTC).

    NemoClaw note
    -------------
    # TODO: wire to NemoClaw when v0.3 stable
    Map: output → NemoClaw.reasoning_output, confidence → certainty_score,
    bdi_metadata → NemoClaw.evidence_chain
    """

    output: str
    producing_node: str = "synthesiser"
    intent_id: str = ""
    complexity: str = "simple"
    confidence: float = 1.0
    model1_calls: int = 0
    model2_calls: int = 0
    escalated: bool = False
    elapsed_ms: float = 0.0
    bdi_metadata: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_json(self) -> str:
        """Serialise to JSON string."""
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> JagaShellResult:
        """Deserialise from JSON string."""
        data = json.loads(json_str)
        return cls(**data)

    def to_dict(self) -> dict:
        """Return as JSON-safe dict."""
        return asdict(self)

    @classmethod
    def from_graph_output(cls, graph_output: dict, intent: JagaShellIntent | None = None) -> JagaShellResult:
        """
        Convenience factory: build a JagaShellResult from a swarm graph output dict.

        Parameters
        ----------
        graph_output:
            Dict returned by graph.run() — expected keys: output, bdi_metadata, node_results.
        intent:
            The original JagaShellIntent this answers (for correlation).
        """
        bdi = graph_output.get("bdi_metadata", {})
        return cls(
            output=graph_output.get("output", ""),
            producing_node=bdi.get("persona", "synthesiser"),
            intent_id=intent.intent_id if intent else "",
            complexity=bdi.get("complexity", "simple"),
            confidence=bdi.get("confidence", 1.0),
            model1_calls=bdi.get("model1_calls", 0),
            model2_calls=bdi.get("model2_calls", 0),
            escalated=bdi.get("escalated", False),
            elapsed_ms=bdi.get("elapsed_ms", 0.0),
            bdi_metadata=bdi,
            metadata={"node_results_count": len(graph_output.get("node_results", {}))},
        )
