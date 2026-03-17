"""
Adaptive Swarm — Dynamic replanning based on execution results.

Wraps existing TaskPlanner with adaptive capabilities:
- Failure pattern detection
- Dynamic strategy adjustment
- Timeout handling
- Fallback tool selection

Usage:
    from jagabot.swarm.adaptive_planner import AdaptivePlanner
    
    planner = AdaptivePlanner()
    plan = planner.plan("Analyze AAPL risk")
    
    # If execution fails:
    plan = planner.replan("Analyze AAPL risk", failures)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from loguru import logger


class FailureType(Enum):
    """Types of execution failures."""
    TIMEOUT = "timeout"
    TOOL_MISSING = "tool_missing"
    DATA_CORRUPTED = "data_corrupted"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    DEPENDENCY_FAILED = "dependency_failed"
    RATE_LIMITED = "rate_limited"
    UNKNOWN = "unknown"


@dataclass
class FailureRecord:
    """Record of a task failure."""
    task_id: str
    tool_name: str
    failure_type: FailureType
    error_message: str
    retry_count: int = 0
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "tool_name": self.tool_name,
            "failure_type": self.failure_type.value,
            "error_message": self.error_message[:200],
            "retry_count": self.retry_count,
            "timestamp": self.timestamp
        }


@dataclass
class TaskPlan:
    """Execution plan with adaptive metadata."""
    task_id: str
    steps: List[Dict[str, Any]]
    strategy: str = "default"
    timeout_multiplier: float = 1.0
    fallback_enabled: bool = True
    max_parallel: int = 8
    validation_enabled: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "steps": self.steps,
            "strategy": self.strategy,
            "timeout_multiplier": self.timeout_multiplier,
            "fallback_enabled": self.fallback_enabled,
            "max_parallel": self.max_parallel,
            "validation_enabled": self.validation_enabled
        }


class AdaptivePlanner:
    """
    Adaptive task planner with dynamic replanning.
    
    Wraps existing TaskPlanner and adds:
    - Failure pattern analysis
    - Strategy adaptation
    - Timeout/resilience handling
    - Fallback tool selection
    """
    
    # Strategy templates
    STRATEGIES = {
        "default": {
            "timeout_multiplier": 1.0,
            "max_parallel": 8,
            "fallback_enabled": False,
            "validation_enabled": False
        },
        "timeout_resilient": {
            "timeout_multiplier": 2.0,
            "max_parallel": 4,
            "fallback_enabled": True,
            "validation_enabled": False
        },
        "fallback_enabled": {
            "timeout_multiplier": 1.5,
            "max_parallel": 8,
            "fallback_enabled": True,
            "validation_enabled": False
        },
        "validation_strict": {
            "timeout_multiplier": 1.5,
            "max_parallel": 4,
            "fallback_enabled": True,
            "validation_enabled": True
        },
        "resource_conservative": {
            "timeout_multiplier": 1.0,
            "max_parallel": 4,
            "fallback_enabled": True,
            "validation_enabled": False
        },
        "dependency_aware": {
            "timeout_multiplier": 1.5,
            "max_parallel": 2,
            "fallback_enabled": True,
            "validation_enabled": True
        }
    }
    
    # Fallback tool mappings
    FALLBACK_MAP = {
        "web_search": ["web_fetch", "researcher"],
        "monte_carlo": ["statistical_engine", "bayesian_reasoner"],
        "swarm_analysis": ["offline_swarm"],
        "decision_engine": ["k3_perspective"],
        "bayesian_reasoner": ["k1_bayesian"],
    }
    
    def __init__(self, workspace: Path | str | None = None):
        self.workspace = Path(workspace) if workspace else Path.home() / ".jagabot" / "workspace"
        
        # Failure tracking
        self.failures: List[FailureRecord] = []
        self.success_patterns: Dict[str, int] = {}
        self.strategy_history: List[str] = []
        
        # Import base planner
        try:
            from jagabot.swarm.planner import TaskPlanner
            self.base_planner = TaskPlanner()
            logger.debug("AdaptivePlanner: using TaskPlanner base")
        except ImportError:
            self.base_planner = None
            logger.warning("AdaptivePlanner: TaskPlanner not available, using fallback")
    
    def plan(self, task: str, context: Dict[str, Any] | None = None) -> TaskPlan:
        """
        Generate initial plan.
        
        Args:
            task: Task description
            context: Optional context dict
        
        Returns:
            TaskPlan with steps and strategy
        """
        # Use base planner if available
        if self.base_planner is not None:
            try:
                plan_groups = self.base_planner._category_tasks(task, context or {})
                steps = self._plan_groups_to_steps(plan_groups)
            except Exception as e:
                logger.warning(f"AdaptivePlanner: base planner failed: {e}")
                steps = self._create_fallback_plan(task)
        else:
            steps = self._create_fallback_plan(task)
        
        # Determine best initial strategy based on task type
        strategy = self._select_initial_strategy(task)
        config = self.STRATEGIES.get(strategy, self.STRATEGIES["default"])
        
        plan = TaskPlan(
            task_id=task,
            steps=steps,
            strategy=strategy,
            timeout_multiplier=config["timeout_multiplier"],
            fallback_enabled=config["fallback_enabled"],
            max_parallel=config["max_parallel"],
            validation_enabled=config["validation_enabled"]
        )
        
        self.strategy_history.append(strategy)
        return plan
    
    def replan(self, task: str, failures: List[FailureRecord]) -> TaskPlan:
        """
        Adapt plan based on failures.
        
        Args:
            task: Original task
            failures: List of failure records
        
        Returns:
            Adapted TaskPlan
        """
        # Record failures
        self.failures.extend(failures)
        
        # Analyze failure patterns
        patterns = self._analyze_failures(failures)
        
        # Select adaptive strategy
        strategy = self._select_adaptive_strategy(patterns)
        config = self.STRATEGIES.get(strategy, self.STRATEGIES["default"])
        
        # Generate new plan
        if self.base_planner is not None:
            try:
                plan_groups = self.base_planner._category_tasks(task, {})
                steps = self._plan_groups_to_steps(plan_groups)
            except Exception:
                steps = self._create_fallback_plan(task)
        else:
            steps = self._create_fallback_plan(task)
        
        # Apply strategy-specific modifications
        steps = self._apply_strategy_modifications(steps, strategy, patterns)
        
        plan = TaskPlan(
            task_id=task,
            steps=steps,
            strategy=strategy,
            timeout_multiplier=config["timeout_multiplier"],
            fallback_enabled=config["fallback_enabled"],
            max_parallel=config["max_parallel"],
            validation_enabled=config["validation_enabled"]
        )
        
        self.strategy_history.append(strategy)
        logger.info(f"AdaptivePlanner: replanned with strategy '{strategy}' after {len(failures)} failures")
        
        return plan
    
    def _analyze_failures(self, failures: List[FailureRecord]) -> Set[FailureType]:
        """Identify failure patterns from recent failures."""
        patterns = set()
        
        for f in failures:
            patterns.add(f.failure_type)
            
            # Detect repeated failures
            tool_failures = sum(1 for ff in self.failures[-10:] if ff.tool_name == f.tool_name)
            if tool_failures >= 3:
                patterns.add(FailureType.TOOL_MISSING)
        
        return patterns
    
    def _select_initial_strategy(self, task: str) -> str:
        """Select initial strategy based on task characteristics."""
        task_lower = task.lower()
        
        # Detect task types
        if any(word in task_lower for word in ["urgent", "quick", "fast"]):
            return "default"
        
        if any(word in task_lower for word in ["complex", "analysis", "deep"]):
            return "validation_strict"
        
        if any(word in task_lower for word in ["large", "many", "batch"]):
            return "resource_conservative"
        
        return "default"
    
    def _select_adaptive_strategy(self, patterns: Set[FailureType]) -> str:
        """Select strategy based on failure patterns."""
        if FailureType.TIMEOUT in patterns:
            return "timeout_resilient"
        
        if FailureType.TOOL_MISSING in patterns:
            return "fallback_enabled"
        
        if FailureType.DATA_CORRUPTED in patterns:
            return "validation_strict"
        
        if FailureType.RESOURCE_EXHAUSTED in patterns:
            return "resource_conservative"
        
        if FailureType.DEPENDENCY_FAILED in patterns:
            return "dependency_aware"
        
        return "default"
    
    def _apply_strategy_modifications(
        self, 
        steps: List[Dict[str, Any]], 
        strategy: str,
        patterns: Set[FailureType]
    ) -> List[Dict[str, Any]]:
        """Apply strategy-specific modifications to plan steps."""
        modified_steps = []
        
        for step in steps:
            modified_step = step.copy()
            
            # Apply timeout adjustments
            if strategy == "timeout_resilient":
                modified_step["timeout"] = int(step.get("timeout", 30) * 2.0)
                modified_step["retry_on_timeout"] = True
            
            # Add fallbacks
            if strategy in ("fallback_enabled", "validation_strict", "dependency_aware"):
                tool_name = step.get("tool", "")
                if tool_name in self.FALLBACK_MAP:
                    modified_step["fallbacks"] = self.FALLBACK_MAP[tool_name]
            
            # Add validation steps
            if strategy == "validation_strict" and step.get("tool"):
                modified_steps.append(modified_step)
                # Add validation after each tool
                modified_steps.append({
                    "tool": "evaluate_result",
                    "action": "anomaly",
                    "is_validation": True,
                    "depends_on": [len(modified_steps) - 1]
                })
                continue
            
            modified_steps.append(modified_step)
        
        return modified_steps
    
    def _plan_groups_to_steps(self, plan_groups: List[List[Any]]) -> List[Dict[str, Any]]:
        """Convert planner groups to step list."""
        steps = []
        
        for group_idx, group in enumerate(plan_groups):
            for task_spec in group:
                step = {
                    "group": group_idx,
                    "tool": getattr(task_spec, 'tool_name', str(task_spec)),
                    "params": getattr(task_spec, 'params', {}),
                    "timeout": 30
                }
                steps.append(step)
        
        return steps
    
    def _create_fallback_plan(self, task: str) -> List[Dict[str, Any]]:
        """Create a simple fallback plan when base planner unavailable."""
        return [
            {
                "group": 0,
                "tool": "researcher",
                "params": {"query": task},
                "timeout": 30
            },
            {
                "group": 1,
                "tool": "decision_engine",
                "params": {"data": {"query": task}},
                "timeout": 30
            }
        ]
    
    def record_success(self, task_id: str, strategy: str):
        """Record successful strategy for future learning."""
        self.success_patterns[strategy] = self.success_patterns.get(strategy, 0) + 1
    
    def get_best_strategy(self) -> str:
        """Get most successful strategy based on history."""
        if not self.success_patterns:
            return "default"
        return max(self.success_patterns, key=self.success_patterns.get)
    
    def get_stats(self) -> Dict[str, Any]:
        """Return planner statistics."""
        return {
            "total_failures": len(self.failures),
            "total_plans": len(self.strategy_history),
            "success_patterns": dict(self.success_patterns),
            "best_strategy": self.get_best_strategy(),
            "recent_strategies": self.strategy_history[-10:]
        }
    
    def clear_history(self):
        """Clear failure and strategy history."""
        self.failures.clear()
        self.strategy_history.clear()


class AdaptivePlannerTool:
    """
    Tool wrapper for AdaptivePlanner.
    Can be used as a jagabot tool for adaptive planning.
    """
    
    def __init__(self, workspace: Path | str | None = None):
        self.planner = AdaptivePlanner(workspace)
    
    async def execute(self, action: str, **kwargs) -> str:
        """
        Execute adaptive planning action.
        
        Args:
            action: One of: plan, replan, stats, best_strategy, clear
            **kwargs: Action-specific parameters
        
        Returns:
            JSON string result
        """
        import json
        
        if action == "plan":
            task = kwargs.get("task", "")
            context = kwargs.get("context", {})
            plan = self.planner.plan(task, context)
            return json.dumps(plan.to_dict())
        
        elif action == "replan":
            task = kwargs.get("task", "")
            failures_data = kwargs.get("failures", [])
            
            # Convert failure dicts to FailureRecord objects
            failures = []
            for fd in failures_data:
                failures.append(FailureRecord(
                    task_id=fd.get("task_id", ""),
                    tool_name=fd.get("tool_name", ""),
                    failure_type=FailureType(fd.get("failure_type", "unknown")),
                    error_message=fd.get("error_message", ""),
                    retry_count=fd.get("retry_count", 0)
                ))
            
            plan = self.planner.replan(task, failures)
            return json.dumps(plan.to_dict())
        
        elif action == "stats":
            result = self.planner.get_stats()
            return json.dumps(result)
        
        elif action == "best_strategy":
            strategy = self.planner.get_best_strategy()
            return json.dumps({"best_strategy": strategy})
        
        elif action == "clear":
            self.planner.clear_history()
            return json.dumps({"cleared": True})
        
        else:
            return json.dumps({"error": f"Unknown action: {action}"})
