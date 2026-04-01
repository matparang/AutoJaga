"""Code generator — produces executable Python from tool name + params.

Two patterns:
  - **Dispatch tools** (method + params): ``tool.execute(method="x", params={...})``
  - **Simple tools** (**kwargs): ``tool.execute(**params)``
"""

from __future__ import annotations

import json
import textwrap
from typing import Any

# tool_name → Python module path (relative to jagabot.agent.tools)
_MODULE_MAP: dict[str, str] = {
    "monte_carlo": "monte_carlo",
    "var": "var",
    "cvar": "cvar",
    "stress_test": "stress_test",
    "early_warning": "early_warning",
    "sensitivity": "sensitivity",
    "financial_cv": "financial_cv",
    "correlation": "correlation",
    "recovery_time": "recovery_time",
    "portfolio_analyzer": "portfolio_analyzer",
    "statistical": "statistical",
    "decision_engine": "decision",
    "k3_perspective": "k3_perspective",
    "k1_bayesian": "k1_bayesian",
    "bayesian_reasoner": "bayesian",
    "knowledge_graph": "knowledge_graph",
    "memory_fleet": "memory_fleet",
    "meta_learning": "meta_learning",
    "evaluation": "evaluation",
    "researcher": "researcher",
    "skill_trigger": "skill_trigger",
    "review": "review",
    "evolution": "evolution",
    "subagent": "subagent",
    "read_file": "filesystem",
    "write_file": "filesystem",
    "edit_file": "filesystem",
    "list_dir": "filesystem",
    "exec": "exec",
    "spawn": "spawn",
    "message": "message",
    "cron": "cron",
    "visualization": "visualization",
    "copywriter": "copywriter",
    "education": "education",
    "accountability": "accountability",
    "self_improver": "self_improver",
    "counterfactual": "counterfactual",
    "counterfactual_sim": "counterfactual",
    "dynamics": "dynamics",
    "dynamics_oracle": "dynamics",
    "pareto": "pareto",
    "pareto_optimizer": "pareto",
    "sensitivity_analyzer": "sensitivity",
    "statistical_engine": "statistical",
    "evaluate_result": "evaluation",
}

# tool_name → ToolClass name
_CLASS_MAP: dict[str, str] = {
    "monte_carlo": "MonteCarloTool",
    "var": "VaRTool",
    "cvar": "CVaRTool",
    "stress_test": "StressTestTool",
    "early_warning": "EarlyWarningTool",
    "sensitivity": "SensitivityTool",
    "financial_cv": "FinancialCVTool",
    "correlation": "CorrelationTool",
    "recovery_time": "RecoveryTimeTool",
    "portfolio_analyzer": "PortfolioAnalyzerTool",
    "statistical": "StatisticalTool",
    "decision_engine": "DecisionTool",
    "k3_perspective": "K3PerspectiveTool",
    "k1_bayesian": "K1BayesianTool",
    "bayesian_reasoner": "BayesianTool",
    "knowledge_graph": "KnowledgeGraphTool",
    "memory_fleet": "MemoryFleetTool",
    "meta_learning": "MetaLearningTool",
    "evaluation": "EvaluationTool",
    "researcher": "ResearcherTool",
    "skill_trigger": "SkillTriggerTool",
    "review": "ReviewTool",
    "evolution": "EvolutionTool",
    "subagent": "SubagentTool",
    "visualization": "VisualizationTool",
    "copywriter": "CopywriterTool",
    "education": "EducationTool",
    "accountability": "AccountabilityTool",
    "self_improver": "SelfImproverTool",
    "counterfactual": "CounterfactualTool",
    "counterfactual_sim": "CounterfactualTool",
    "dynamics": "DynamicsTool",
    "dynamics_oracle": "DynamicsTool",
    "pareto": "ParetoTool",
    "pareto_optimizer": "ParetoTool",
    "sensitivity_analyzer": "SensitivityTool",
    "statistical_engine": "StatisticalTool",
    "evaluate_result": "EvaluationTool",
}


class CodeGenerator:
    """Generate executable Python code snippets for tool invocations."""

    def generate(
        self,
        tool_name: str,
        params: dict[str, Any],
        method: str | None = None,
    ) -> str:
        """Return a runnable Python snippet."""
        module = _MODULE_MAP.get(tool_name, tool_name)
        cls_name = _CLASS_MAP.get(tool_name)

        if cls_name:
            return self._generate_class(module, cls_name, tool_name, params, method)
        return self._generate_fallback(tool_name, params, method)

    @staticmethod
    def _generate_class(
        module: str,
        cls_name: str,
        tool_name: str,
        params: dict[str, Any],
        method: str | None,
    ) -> str:
        import_line = f"from jagabot.agent.tools.{module} import {cls_name}"
        lines = [
            "import asyncio",
            "import json",
            "",
            import_line,
            "",
            f"tool = {cls_name}()",
        ]

        if method:
            # Dispatch pattern
            inner = params.get("params", {})
            params_str = json.dumps(inner, indent=2, default=str)
            lines += [
                f"result = asyncio.run(tool.execute(",
                f'    method="{method}",',
                f"    params={params_str},",
                f"))",
            ]
        else:
            # Simple pattern — exclude 'method' key if present
            clean = {k: v for k, v in params.items() if k != "method"}
            if clean:
                params_str = json.dumps(clean, indent=2, default=str)
                lines += [
                    f"result = asyncio.run(tool.execute(",
                    f"    **{params_str},",
                    f"))",
                ]
            else:
                lines.append("result = asyncio.run(tool.execute())")

        lines += [
            "",
            "print(json.dumps(result, indent=2, default=str))"
            " if isinstance(result, dict) else print(result)",
        ]
        return "\n".join(lines)

    @staticmethod
    def _generate_fallback(
        tool_name: str, params: dict[str, Any], method: str | None
    ) -> str:
        params_str = json.dumps(params, indent=2, default=str)
        return textwrap.dedent(f"""\
            # Tool: {tool_name}
            # (class mapping not found — using generic template)
            import asyncio, json
            from jagabot.agent.tools import {tool_name}

            params = {params_str}
            # Execute and display result
            print(params)
        """)
