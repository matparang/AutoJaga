"""
InferenceTool — gives agent access to logical inference engine.

Actions:
  add_fact  — add a verified fact triple
  query     — find inference chain between two concepts
  infer_all — all conclusions reachable from a concept
  stats     — show inference engine statistics
"""

from __future__ import annotations
from pathlib import Path
from jagabot.agent.tools.base import Tool


class InferenceTool(Tool):
    name = "inference"
    description = (
        "Logical inference engine — store facts and derive multi-hop conclusions. "
        "add_fact: store verified fact. query: find reasoning chain between concepts. "
        "infer_all: all conclusions from a concept. stats: show fact database."
    )

    def __init__(self, workspace: Path = None):
        self._workspace = workspace or Path("/root/.jagabot")
        self._engine    = None

    def _get_engine(self):
        if self._engine is None:
            from jagabot.core.logical_inference import LogicalInferenceChain
            self._engine = LogicalInferenceChain(self._workspace)
        return self._engine

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add_fact", "query", "infer_all", "stats"],
                },
                "subject":    {"type": "string", "description": "Source concept e.g. 'NVDA'"},
                "predicate":  {"type": "string", "description": "Relation e.g. 'has', 'implies', 'causes'"},
                "object_":    {"type": "string", "description": "Target concept e.g. 'high_volatility'"},
                "confidence": {"type": "number", "description": "Confidence 0-1 (default 0.8)"},
                "evidence":   {"type": "string", "description": "Source of this fact"},
                "domain":     {"type": "string", "description": "Domain: financial/risk/general"},
                "max_hops":   {"type": "integer", "description": "Max hops for inference (default 3)"},
            },
            "required": ["action"],
        }

    def to_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(self, action: str, **kwargs) -> str:
        engine = self._get_engine()

        if action == "add_fact":
            subject    = kwargs.get("subject", "")
            predicate  = kwargs.get("predicate", "")
            object_    = kwargs.get("object_", "")
            confidence = float(kwargs.get("confidence", 0.8))
            evidence   = kwargs.get("evidence", "")
            domain     = kwargs.get("domain", "general")

            if not all([subject, predicate, object_]):
                return "Error: add_fact requires subject, predicate, and object_"

            fact_id = engine.add_fact(
                subject, predicate, object_,
                confidence=confidence, evidence=evidence, domain=domain
            )
            return (
                f"✅ Fact stored: '{subject}' --[{predicate}]--> '{object_}' "
                f"(conf={confidence:.0%}, id={fact_id})"
            )

        elif action == "query":
            subject  = kwargs.get("subject", "")
            object_  = kwargs.get("object_", "")
            max_hops = int(kwargs.get("max_hops", 3))

            if not subject or not object_:
                return "Error: query requires subject and object_"

            chain = engine.query(subject, object_, max_hops=max_hops)
            if chain:
                return engine.explain_chain(chain)
            return f"No inference chain found: '{subject}' → '{object_}' (searched up to {max_hops} hops)"

        elif action == "infer_all":
            subject  = kwargs.get("subject", "")
            max_hops = int(kwargs.get("max_hops", 2))

            if not subject:
                return "Error: infer_all requires subject"

            results = engine.infer_all_from(subject, max_hops=max_hops)
            if not results:
                return f"No inferences found from '{subject}'"

            lines = [f"## All conclusions from '{subject}':"]
            for conclusion, conf, path in results[:10]:
                lines.append(f"  • {conclusion} ({conf:.0%}) via: {path}")
            return "\n".join(lines)

        elif action == "stats":
            stats = engine.get_stats()
            return (
                f"Inference Engine Stats:\n"
                f"  Facts: {stats['total_facts']} ({stats['verified_facts']} verified)\n"
                f"  Inferences run: {stats['total_inferences']}\n"
                f"  Avg hops: {stats['avg_hops']}\n"
                f"  Avg confidence: {stats['avg_confidence']:.0%}\n"
                f"  Domains: {stats['domains']}"
            )

        return f"Unknown action: {action}"
