"""Lab tool registry — discovers and categorises all JAGABOT tools.

Does NOT modify the Tool ABC. Metadata is layered on top of the existing
tool.name / tool.description / tool.parameters properties.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Category mapping: tool_name → category
_TOOL_CATEGORIES: dict[str, str] = {
    # Risk
    "monte_carlo": "risk",
    "var": "risk",
    "cvar": "risk",
    "stress_test": "risk",
    "early_warning": "risk",
    "sensitivity": "risk",
    "sensitivity_analyzer": "risk",
    # Probability / Statistics
    "financial_cv": "probability",
    "correlation": "probability",
    "recovery_time": "probability",
    "portfolio_analyzer": "probability",
    "statistical": "probability",
    "statistical_engine": "probability",
    # Decision
    "decision_engine": "decision",
    "k3_perspective": "decision",
    "k1_bayesian": "decision",
    "bayesian_reasoner": "decision",
    # Analysis
    "knowledge_graph": "analysis",
    "memory_fleet": "analysis",
    "meta_learning": "analysis",
    "evaluation": "analysis",
    "evaluate_result": "analysis",
    "researcher": "analysis",
    # Skills / Orchestration
    "skill_trigger": "skills",
    "review": "skills",
    "evolution": "skills",
    "subagent": "skills",
    # Utility
    "read_file": "utility",
    "write_file": "utility",
    "edit_file": "utility",
    "list_dir": "utility",
    "exec": "utility",
    "spawn": "utility",
    "message": "utility",
    "cron": "utility",
    "visualization": "utility",
    "copywriter": "utility",
    "education": "utility",
    "accountability": "utility",
    "self_improver": "utility",
    "counterfactual": "utility",
    "counterfactual_sim": "utility",
    "dynamics": "utility",
    "dynamics_oracle": "utility",
    "pareto": "utility",
    "pareto_optimizer": "utility",
}


class LabToolRegistry:
    """Discovers all registered tools and layers on Lab metadata."""

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}
        self._categories: dict[str, list[str]] = {}
        self._discover()

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _discover(self) -> None:
        """Import ALL_TOOLS and build internal catalogue."""
        try:
            from jagabot.guardian.tools import ALL_TOOLS
        except ImportError:
            logger.warning("Cannot import ALL_TOOLS – lab registry empty")
            return

        for tool_cls in ALL_TOOLS:
            try:
                tool = tool_cls()
                name = tool.name
                methods = self._extract_methods(tool)
                category = _TOOL_CATEGORIES.get(name, "other")

                self._tools[name] = {
                    "tool": tool,
                    "name": name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "category": category,
                    "methods": methods,
                }

                self._categories.setdefault(category, []).append(name)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Skipping tool %s: %s", tool_cls.__name__, exc)

    @staticmethod
    def _extract_methods(tool: Any) -> list[str]:
        """Extract dispatch methods from a tool (if any)."""
        # Check for _DISPATCH dict on the tool class
        dispatch = getattr(tool.__class__, "_DISPATCH", None)
        if dispatch and isinstance(dispatch, dict):
            return sorted(dispatch.keys())

        # Check JSON Schema enum for 'method' parameter
        params = tool.parameters or {}
        props = params.get("properties", {})
        method_prop = props.get("method", {})
        enum = method_prop.get("enum")
        if enum:
            return list(enum)

        return []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_tools(self) -> dict[str, dict[str, Any]]:
        """Return all tools: {name: {tool, name, description, parameters, category, methods}}."""
        return dict(self._tools)

    def get_tool_info(self, name: str) -> dict[str, Any]:
        """Return info dict for a single tool (empty dict if unknown)."""
        return self._tools.get(name, {})

    def get_categories(self) -> dict[str, list[str]]:
        """Return {category: [tool_names]}."""
        return dict(self._categories)

    def get_tool_methods(self, name: str) -> list[str]:
        """Return dispatch method names for a tool (empty list if simple)."""
        info = self._tools.get(name, {})
        return info.get("methods", [])

    def tool_count(self) -> int:
        """Total number of discovered tools."""
        return len(self._tools)
