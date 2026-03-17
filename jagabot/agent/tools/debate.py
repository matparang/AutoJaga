"""Debate tool — runs multi-persona debates via the autoresearch debate system."""

import json
import sys
from pathlib import Path
from typing import Any

from jagabot.agent.tools.base import Tool

# Ensure autoresearch is importable
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class DebateTool(Tool):
    """Run a structured multi-persona debate (Bull / Bear / Buffett)."""

    @property
    def name(self) -> str:
        return "debate"

    @property
    def description(self) -> str:
        return (
            "Run a multi-persona debate on any topic. "
            "Returns a structured report with arguments, positions, "
            "epistemic quality scores, and cost breakdown."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The debate topic or question",
                },
                "personas": {
                    "type": "string",
                    "description": (
                        "Comma-separated persona names (default: bull,bear,buffett)"
                    ),
                },
                "max_rounds": {
                    "type": "integer",
                    "description": "Maximum debate rounds (default: 3)",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["topic"],
        }

    async def execute(
        self,
        topic: str,
        personas: str | None = None,
        max_rounds: int = 3,
        **kwargs: Any,
    ) -> str:
        try:
            from autoresearch.debate_orchestrator import PersonaDebateOrchestrator

            persona_list = (
                [p.strip() for p in personas.split(",") if p.strip()]
                if personas
                else ["bull", "bear", "buffett"]
            )

            # Save reports to the agent workspace so user can find them
            workspace = Path.home() / ".jagabot" / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)

            orchestrator = PersonaDebateOrchestrator(
                topic=topic,
                personas=persona_list,
                max_rounds=max_rounds,
                report_dir=workspace,
            )
            report = await orchestrator.run_debate()
            return self._format_report(report)

        except Exception as e:
            return f"Error running debate: {e}"

    # ------------------------------------------------------------------
    @staticmethod
    def _format_report(report: dict[str, Any]) -> str:
        w = 60
        lines = [f"\n{'=' * w}", f"🎯 DEBATE: {report.get('topic', '?')}", f"{'=' * w}"]

        # Final positions
        lines.append("\n📊 FINAL POSITIONS:")
        for persona, data in report.get("final_positions", {}).items():
            emoji = {"bull": "🐂", "bear": "🐻", "buffett": "🧔"}.get(persona, "👤")
            score = data if isinstance(data, (int, float)) else data.get("position", "?")
            lines.append(f"  {emoji} {persona.capitalize()}: {score}")

        lines.append(f"\n🔄 Rounds completed: {report.get('rounds_completed', 0)}")
        lines.append(
            f"✅ Consensus: {'YES' if report.get('consensus_reached') else 'NO'}"
        )

        # Epistemic quality
        eq = report.get("epistemic_quality")
        if eq:
            lines.append("\n🧪 Epistemic Quality:")
            for k, v in eq.items():
                lines.append(f"  • {k}: {v}")

        # Cost
        mu = report.get("model_usage", {})
        if mu:
            cost = mu.get("daily_cost_usd", 0)
            lines.append(f"\n💰 Cost: ${cost:.6f}")

        # Fact citations
        fc = report.get("fact_citations")
        if fc:
            lines.append(f"📚 Facts cited: {len(fc)}")

        lines.append(f"{'=' * w}")

        # Also append raw JSON for programmatic use
        lines.append("\n<json_report>")
        lines.append(json.dumps(report, indent=2, default=str))
        lines.append("</json_report>")

        return "\n".join(lines)
