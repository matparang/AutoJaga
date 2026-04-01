"""
Dynamic Skill System — Runtime skill composition and evolution.

Allows jagabot to compose new skills from existing ones at runtime,
track skill performance, and evolve skills based on outcomes.

Usage:
    from jagabot.skills.dynamic_skill import DynamicSkill
    
    skills = DynamicSkill(workspace=Path.home() / ".jagabot" / "workspace")
    
    # Compose a new skill
    skills.compose_skill(
        name="risk_analysis_pro",
        steps=["financial_cv", "monte_carlo", "decision_engine"]
    )
    
    # Execute composed skill
    result = skills.execute("risk_analysis_pro", data={...})
    
    # Track performance
    skills.record_outcome("risk_analysis_pro", success=True, duration=2.5)
    
    # Get best performing skill
    best = skills.get_best_skill("analysis")
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from loguru import logger


class SkillPerformance:
    """Performance tracking for a single skill."""
    
    def __init__(self, name: str):
        self.name = name
        self.calls: int = 0
        self.successes: int = 0
        self.failures: int = 0
        self.total_duration: float = 0.0
        self.last_used: Optional[datetime] = None
        self.outcomes: List[Dict[str, Any]] = []
    
    def record(self, success: bool, duration: float, metadata: Dict[str, Any] | None = None):
        """Record a skill execution outcome."""
        self.calls += 1
        if success:
            self.successes += 1
        else:
            self.failures += 1
        self.total_duration += duration
        self.last_used = datetime.now()
        
        self.outcomes.append({
            "success": success,
            "duration": duration,
            "timestamp": datetime.now().isoformat(),
            **(metadata or {})
        })
        
        # Keep only last 100 outcomes
        if len(self.outcomes) > 100:
            self.outcomes = self.outcomes[-100:]
    
    @property
    def success_rate(self) -> float:
        if self.calls == 0:
            return 0.0
        return self.successes / self.calls
    
    @property
    def avg_duration(self) -> float:
        if self.calls == 0:
            return 0.0
        return self.total_duration / self.calls
    
    @property
    def recent_success_rate(self) -> float:
        """Success rate over last 20 outcomes."""
        recent = self.outcomes[-20:]
        if not recent:
            return self.success_rate
        successes = sum(1 for o in recent if o.get("success", False))
        return successes / len(recent)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "calls": self.calls,
            "successes": self.successes,
            "failures": self.failures,
            "success_rate": round(self.success_rate, 4),
            "recent_success_rate": round(self.recent_success_rate, 4),
            "avg_duration": round(self.avg_duration, 4),
            "last_used": self.last_used.isoformat() if self.last_used else None
        }


class DynamicSkill:
    """
    Dynamic skill composition and execution system.
    
    Features:
    - Compose new skills from existing tool sequences
    - Track performance metrics per skill
    - Evolve skills based on outcomes
    - Persist skill definitions and performance
    """
    
    def __init__(self, workspace: Path | str | None = None):
        self.workspace = Path(workspace) if workspace else Path.home() / ".jagabot" / "workspace"
        self.skills_dir = self.workspace / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        
        # Skill storage
        self.skill_definitions: Dict[str, Dict[str, Any]] = {}
        self.performance: Dict[str, SkillPerformance] = {}
        
        # Load existing skills
        self._load_skills()
        
        # Import tool registry for execution
        try:
            from jagabot.agent.tools.registry import ToolRegistry
            self.tools = ToolRegistry()
            self._has_tools = True
        except ImportError:
            self.tools = None
            self._has_tools = False
            logger.warning("DynamicSkill: ToolRegistry not available")
    
    def _load_skills(self):
        """Load existing skill definitions from disk."""
        skills_file = self.skills_dir / "dynamic_skills.json"
        if not skills_file.exists():
            return
        
        try:
            data = json.loads(skills_file.read_text())
            self.skill_definitions = data.get("definitions", {})
            
            # Load performance data
            for name, perf_data in data.get("performance", {}).items():
                perf = SkillPerformance(name)
                perf.calls = perf_data.get("calls", 0)
                perf.successes = perf_data.get("successes", 0)
                perf.failures = perf_data.get("failures", 0)
                perf.total_duration = perf_data.get("total_duration", 0.0)
                if last_used := perf_data.get("last_used"):
                    perf.last_used = datetime.fromisoformat(last_used)
                self.performance[name] = perf
            
            logger.debug(f"DynamicSkill: loaded {len(self.skill_definitions)} skills")
        except Exception as e:
            logger.warning(f"DynamicSkill: failed to load skills: {e}")
    
    def _save_skills(self):
        """Persist skill definitions and performance to disk."""
        skills_file = self.skills_dir / "dynamic_skills.json"
        
        data = {
            "definitions": self.skill_definitions,
            "performance": {name: perf.to_dict() for name, perf in self.performance.items()}
        }
        
        try:
            skills_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"DynamicSkill: failed to save skills: {e}")
    
    def compose_skill(self, name: str, steps: List[str], metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Compose a new skill from existing tools.
        
        Args:
            name: Skill name
            steps: List of tool names to execute in sequence
            metadata: Optional metadata (description, tags, etc.)
        
        Returns:
            Skill definition dict
        """
        definition = {
            "name": name,
            "steps": steps,
            "type": "composed",
            "created_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        self.skill_definitions[name] = definition
        self.performance[name] = SkillPerformance(name)
        self._save_skills()
        
        logger.info(f"DynamicSkill: composed '{name}' with {len(steps)} steps")
        return definition
    
    def register_skill(self, name: str, func: Callable, metadata: Dict[str, Any] | None = None):
        """
        Register a custom skill function.
        
        Args:
            name: Skill name
            func: Callable to execute
            metadata: Optional metadata
        """
        definition = {
            "name": name,
            "type": "custom",
            "created_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        self.skill_definitions[name] = definition
        self.performance[name] = SkillPerformance(name)
        
        # Store function reference (not serializable)
        setattr(self, f"_func_{name}", func)
        self._save_skills()
        
        logger.info(f"DynamicSkill: registered custom skill '{name}'")
    
    async def execute(self, name: str, data: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Execute a composed skill.
        
        Args:
            name: Skill name
            data: Input data for the skill
        
        Returns:
            Execution result dict
        """
        if name not in self.skill_definitions:
            return {"error": f"Skill '{name}' not found"}
        
        definition = self.skill_definitions[name]
        start_time = time.time()
        
        try:
            if definition["type"] == "composed":
                result = await self._execute_composed(name, definition, data or {})
            elif definition["type"] == "custom":
                result = await self._execute_custom(name, definition, data or {})
            else:
                result = {"error": f"Unknown skill type: {definition['type']}"}
            
            duration = time.time() - start_time
            self.performance[name].record(success=True, duration=duration, metadata={"result": str(result)[:100]})
            self._save_skills()
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self.performance[name].record(success=False, duration=duration, metadata={"error": str(e)})
            self._save_skills()
            
            return {"error": str(e)}
    
    async def _execute_composed(self, name: str, definition: Dict, data: Dict) -> Dict:
        """Execute a composed skill (sequence of tools)."""
        if not self._has_tools:
            return {"error": "ToolRegistry not available"}
        
        results = []
        current_data = data
        
        for step in definition["steps"]:
            # Execute tool
            try:
                tool = self.tools.get(step)
                if tool is None:
                    return {"error": f"Tool '{step}' not found"}
                
                # Execute with current data
                result = await tool.execute(**current_data)
                results.append({"step": step, "result": result})
                
                # Pass result to next step (if dict)
                if isinstance(result, dict):
                    current_data = {**current_data, **result}
                    
            except Exception as e:
                logger.warning(f"DynamicSkill: step '{step}' failed: {e}")
                return {"error": f"Step '{step}' failed: {e}", "partial_results": results}
        
        return {
            "skill": name,
            "steps_completed": len(results),
            "results": results,
            "final_data": current_data
        }
    
    async def _execute_custom(self, name: str, definition: Dict, data: Dict) -> Dict:
        """Execute a custom skill function."""
        func = getattr(self, f"_func_{name}", None)
        if func is None:
            return {"error": f"Custom function for '{name}' not found"}
        
        if callable(func):
            result = func(data)
            if hasattr(result, '__await__'):
                result = await result
            return result
        
        return {"error": f"Registered function for '{name}' is not callable"}
    
    def record_outcome(self, name: str, success: bool, duration: float, metadata: Dict[str, Any] | None = None):
        """
        Record outcome for a skill execution.
        
        Args:
            name: Skill name
            success: Whether execution was successful
            duration: Execution duration in seconds
            metadata: Optional metadata
        """
        if name not in self.performance:
            self.performance[name] = SkillPerformance(name)
        
        self.performance[name].record(success, duration, metadata)
        self._save_skills()
    
    def get_performance(self, name: str) -> Dict[str, Any]:
        """Get performance metrics for a skill."""
        if name not in self.performance:
            return {"error": f"Skill '{name}' not found"}
        return self.performance[name].to_dict()
    
    def get_best_skill(self, category: str | None = None, min_calls: int = 5) -> str | None:
        """
        Get best performing skill by success rate.
        
        Args:
            category: Optional category filter
            min_calls: Minimum number of calls required
        
        Returns:
            Best skill name or None
        """
        candidates = []
        
        for name, perf in self.performance.items():
            if perf.calls < min_calls:
                continue
            
            # Filter by category if specified
            if category:
                skill_def = self.skill_definitions.get(name, {})
                metadata = skill_def.get("metadata", {})
                if metadata.get("category") != category:
                    continue
            
            candidates.append((name, perf.recent_success_rate))
        
        if not candidates:
            return None
        
        # Sort by recent success rate
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    
    def get_rankings(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get skill performance rankings.
        
        Args:
            limit: Maximum number of skills to return
        
        Returns:
            List of performance dicts sorted by success rate
        """
        rankings = [perf.to_dict() for perf in self.performance.values()]
        rankings.sort(key=lambda x: x["recent_success_rate"], reverse=True)
        return rankings[:limit]
    
    def evolve_skill(self, name: str, new_steps: List[str] | None = None, metadata: Dict[str, Any] | None = None):
        """
        Evolve a skill by modifying its definition.
        
        Args:
            name: Skill name
            new_steps: Optional new step sequence
            metadata: Optional metadata updates
        """
        if name not in self.skill_definitions:
            return {"error": f"Skill '{name}' not found"}
        
        definition = self.skill_definitions[name]
        
        if new_steps:
            definition["steps"] = new_steps
            definition["version"] = definition.get("version", 1) + 1
            definition["evolved_at"] = datetime.now().isoformat()
        
        if metadata:
            definition["metadata"] = {**definition.get("metadata", {}), **metadata}
        
        # Reset performance on evolution
        self.performance[name] = SkillPerformance(name)
        
        self._save_skills()
        logger.info(f"DynamicSkill: evolved '{name}'")
        return definition
    
    def delete_skill(self, name: str) -> bool:
        """Delete a skill."""
        if name not in self.skill_definitions:
            return False
        
        del self.skill_definitions[name]
        if name in self.performance:
            del self.performance[name]
        
        self._save_skills()
        return True
    
    def list_skills(self) -> List[str]:
        """List all skill names."""
        return list(self.skill_definitions.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get overall skill system statistics."""
        total_calls = sum(p.calls for p in self.performance.values())
        total_successes = sum(p.successes for p in self.performance.values())
        
        return {
            "total_skills": len(self.skill_definitions),
            "total_calls": total_calls,
            "overall_success_rate": round(total_successes / total_calls, 4) if total_calls > 0 else 0.0,
            "skills_with_data": sum(1 for p in self.performance.values() if p.calls > 0)
        }


class DynamicSkillTool:
    """
    Tool wrapper for DynamicSkill.
    Can be used as a jagabot tool for skill operations.
    """
    
    def __init__(self, workspace: Path | str | None = None):
        self.skills = DynamicSkill(workspace)
    
    async def execute(self, action: str, **kwargs) -> str:
        """
        Execute dynamic skill action.
        
        Args:
            action: One of: compose, execute, evolve, delete, list, stats, rankings, best, performance
            **kwargs: Action-specific parameters
        
        Returns:
            JSON string result
        """
        import json
        
        if action == "compose":
            name = kwargs.get("name", "")
            steps = kwargs.get("steps", [])
            metadata = kwargs.get("metadata", {})
            result = self.skills.compose_skill(name, steps, metadata)
            return json.dumps(result)
        
        elif action == "execute":
            name = kwargs.get("name", "")
            data = kwargs.get("data", {})
            result = await self.skills.execute(name, data)
            return json.dumps(result)
        
        elif action == "evolve":
            name = kwargs.get("name", "")
            new_steps = kwargs.get("new_steps")
            metadata = kwargs.get("metadata")
            result = self.skills.evolve_skill(name, new_steps, metadata)
            return json.dumps(result)
        
        elif action == "delete":
            name = kwargs.get("name", "")
            success = self.skills.delete_skill(name)
            return json.dumps({"deleted": success})
        
        elif action == "list":
            skills = self.skills.list_skills()
            return json.dumps({"skills": skills, "count": len(skills)})
        
        elif action == "stats":
            result = self.skills.get_stats()
            return json.dumps(result)
        
        elif action == "rankings":
            limit = kwargs.get("limit", 10)
            result = self.skills.get_rankings(limit)
            return json.dumps({"rankings": result})
        
        elif action == "best":
            category = kwargs.get("category")
            min_calls = kwargs.get("min_calls", 5)
            best = self.skills.get_best_skill(category, min_calls)
            return json.dumps({"best_skill": best})
        
        elif action == "performance":
            name = kwargs.get("name", "")
            result = self.skills.get_performance(name)
            return json.dumps(result)
        
        else:
            return json.dumps({"error": f"Unknown action: {action}"})
