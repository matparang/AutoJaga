"""
SkillComposer — composable skill workflows where skills call other skills.

A workflow is an ordered list of steps.  Each step references a skill
(typically a tool action), feeds context forward, and optionally applies
a review gate before proceeding.

The composer does NOT execute tools directly — it builds a structured
execution plan that the agent loop or SubagentManager can run.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowStep:
    """One step in a composable workflow."""

    skill: str          # tool or skill name to invoke
    action: str         # action within that tool
    params: dict = field(default_factory=dict)
    pass_output_as: str | None = None   # key to inject previous output
    review_after: bool = False          # run TwoStageReview after this step
    description: str = ""


@dataclass
class Workflow:
    """An ordered sequence of WorkflowSteps."""

    name: str
    description: str
    steps: list[WorkflowStep] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


# ------------------------------------------------------------------
# Default financial workflows
# ------------------------------------------------------------------

_DEFAULT_WORKFLOWS: list[Workflow] = [
    Workflow(
        name="crisis_management",
        description="Full crisis response: review portfolio → validate risk → check advisors → Monte Carlo → action plan",
        tags=["crisis", "risk", "portfolio"],
        steps=[
            WorkflowStep(
                skill="portfolio_analyzer",
                action="analyze",
                description="Assess current portfolio exposure",
            ),
            WorkflowStep(
                skill="var",
                action="calculate",
                pass_output_as="portfolio_data",
                description="Calculate Value-at-Risk",
            ),
            WorkflowStep(
                skill="stress_test",
                action="run",
                pass_output_as="risk_data",
                description="Run stress scenarios",
            ),
            WorkflowStep(
                skill="monte_carlo",
                action="simulate",
                pass_output_as="stress_results",
                review_after=True,
                description="Monte Carlo with evolved parameters",
            ),
            WorkflowStep(
                skill="evaluate_result",
                action="full",
                pass_output_as="simulation",
                description="Quality gate on simulation",
            ),
        ],
    ),
    Workflow(
        name="investment_thesis",
        description="Structured thesis: clarify → explore → present → save",
        tags=["thesis", "research", "investment"],
        steps=[
            WorkflowStep(
                skill="financial_cv",
                action="analyze",
                description="Analyse asset volatility regime",
            ),
            WorkflowStep(
                skill="bayesian",
                action="assess",
                pass_output_as="cv_result",
                description="Bayesian probability assessment",
            ),
            WorkflowStep(
                skill="multi_perspective",
                action="collapse",
                pass_output_as="bayesian_result",
                description="Bull/Bear/Buffet analysis",
            ),
            WorkflowStep(
                skill="evaluate_result",
                action="evaluate",
                pass_output_as="perspectives",
                review_after=True,
                description="Evaluate thesis quality",
            ),
        ],
    ),
    Workflow(
        name="risk_validation",
        description="TDD-style risk validation: define expectations → calculate → compare → refactor",
        tags=["risk", "validation", "tdd"],
        steps=[
            WorkflowStep(
                skill="var",
                action="calculate",
                description="RED: define expected VaR",
            ),
            WorkflowStep(
                skill="cvar",
                action="calculate",
                pass_output_as="var_result",
                description="GREEN: calculate actual CVaR",
            ),
            WorkflowStep(
                skill="correlation",
                action="analyze",
                pass_output_as="cvar_result",
                description="GREEN: check correlation matrix",
            ),
            WorkflowStep(
                skill="evaluate_result",
                action="evaluate",
                pass_output_as="correlation_data",
                review_after=True,
                description="REFACTOR: compare expected vs actual",
            ),
        ],
    ),
    Workflow(
        name="portfolio_rebalancing",
        description="Rebalance: verify allocation → present options → generate trade list",
        tags=["portfolio", "rebalance", "allocation"],
        steps=[
            WorkflowStep(
                skill="portfolio_analyzer",
                action="analyze",
                description="Verify current allocation vs target",
            ),
            WorkflowStep(
                skill="sensitivity",
                action="analyze",
                pass_output_as="portfolio_data",
                description="Sensitivity of allocation changes",
            ),
            WorkflowStep(
                skill="monte_carlo",
                action="simulate",
                pass_output_as="sensitivity_result",
                review_after=True,
                description="Simulate rebalanced portfolio",
            ),
        ],
    ),
]


class SkillComposer:
    """Manage and execute composable skill workflows."""

    def __init__(self, workflows: list[Workflow] | None = None):
        self._workflows: dict[str, Workflow] = {}
        for wf in (workflows or _DEFAULT_WORKFLOWS):
            self._workflows[wf.name] = wf

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_workflow(self, name: str) -> list[dict] | None:
        """Return steps for a named workflow, or None if not found."""
        wf = self._workflows.get(name)
        if not wf:
            return None
        return [
            {
                "skill": s.skill,
                "action": s.action,
                "params": s.params,
                "pass_output_as": s.pass_output_as,
                "review_after": s.review_after,
                "description": s.description,
            }
            for s in wf.steps
        ]

    def compose(self, name: str, context: dict[str, Any] | None = None) -> dict:
        """Build a full execution plan for a workflow.

        Returns::

            {
                "workflow": "crisis_management",
                "steps": [...],
                "context": {...},
                "step_count": 5,
            }

        Does NOT execute the steps — the agent loop handles execution.
        """
        wf = self._workflows.get(name)
        if not wf:
            return {"error": f"Unknown workflow: {name}", "workflow": name}

        ctx = dict(context or {})
        plan_steps: list[dict] = []

        for step in wf.steps:
            params = dict(step.params)
            if step.pass_output_as and plan_steps:
                params[step.pass_output_as] = f"{{output_of_step_{len(plan_steps) - 1}}}"

            plan_steps.append(
                {
                    "step": len(plan_steps),
                    "skill": step.skill,
                    "action": step.action,
                    "params": params,
                    "review_after": step.review_after,
                    "description": step.description,
                }
            )

        return {
            "workflow": name,
            "description": wf.description,
            "steps": plan_steps,
            "context": ctx,
            "step_count": len(plan_steps),
        }

    def register_workflow(
        self,
        name: str,
        steps: list[WorkflowStep],
        description: str = "",
        tags: list[str] | None = None,
    ) -> Workflow:
        """Add or replace a workflow at runtime."""
        wf = Workflow(
            name=name,
            description=description,
            steps=list(steps),
            tags=tags or [],
        )
        self._workflows[name] = wf
        return wf

    def list_workflows(self) -> list[dict]:
        """Return metadata for all registered workflows."""
        return [
            {
                "name": wf.name,
                "description": wf.description,
                "step_count": len(wf.steps),
                "tags": wf.tags,
            }
            for wf in self._workflows.values()
        ]

    def remove_workflow(self, name: str) -> bool:
        """Remove a workflow by name. Returns True if removed."""
        return self._workflows.pop(name, None) is not None
