# jagabot/swarm/parallel_runner.py
"""
ParallelRunner — Real parallel multi-agent execution via asyncio.gather

Unlike sequential subagents, ParallelRunner spawns multiple agents that
run SIMULTANEOUSLY and converge their results.

Use cases:
1. K3 Perspectives: Run Bull/Bear/Buffet in parallel, then arbitrate
2. Multi-Strategy: Test multiple approaches simultaneously
3. Ensemble: Run multiple agents and aggregate results

Wire into loop.py __init__:
    from jagabot.swarm.parallel_runner import ParallelRunner
    self.parallel_runner = ParallelRunner(
        provider=provider,
        workspace=workspace,
        brier_scorer=None,  # wired after brier init
    )

Usage in loop.py _process_message:
    if should_run_parallel:
        result = await self.parallel_runner.run(
            task=msg.content,
            agents=[
                {"role": "bull", "system": "Optimistic analyst..."},
                {"role": "bear", "system": "Pessimistic analyst..."},
                {"role": "buffet", "system": "Conservative value investor..."},
            ],
            converge_via="arbitration",  # or "voting" | "llm_summary"
        )
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from jagabot.providers.base import LLMProvider
from jagabot.agent.tools.registry import ToolRegistry


@dataclass
class AgentResult:
    """Result from one parallel agent."""
    role: str
    output: str
    confidence: float = 0.5
    tools_used: list = field(default_factory=list)
    iterations: int = 0
    error: Optional[str] = None


@dataclass
class ParallelResult:
    """Aggregated result from parallel execution."""
    agent_results: list[AgentResult]
    converged_output: str
    convergence_method: str
    total_time_ms: float
    winner: Optional[str] = None  # if arbitration used


class ParallelRunner:
    """
    Executes multiple agents in parallel and converges results.
    
    Key difference from SubagentManager:
    - Subagents run SEQUENTIALLY (one after another)
    - ParallelRunner runs SIMULTANEOUSLY (asyncio.gather)
    """
    
    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        brier_scorer: Any = None,
        max_parallel: int = 5,
        timeout_seconds: int = 120,
    ) -> None:
        self.provider = provider
        self.workspace = workspace
        self.brier_scorer = brier_scorer
        self.max_parallel = max_parallel
        self.timeout_seconds = timeout_seconds
    
    async def run(
        self,
        task: str,
        agents: list[dict],
        converge_via: str = "arbitration",
        tools: Optional[ToolRegistry] = None,
    ) -> ParallelResult:
        """
        Run multiple agents in parallel and converge results.
        
        Args:
            task: The task for all agents to solve
            agents: List of {role, system, model?} configs
            converge_via: How to converge results
                - "arbitration": Use BrierScorer to pick winner
                - "voting": Simple majority vote
                - "llm_summary": LLM summarizes all outputs
            tools: Optional shared tool registry
        
        Returns:
            ParallelResult with all agent outputs and converged answer
        """
        t_start = datetime.now()
        
        # Create parallel tasks
        tasks = [
            asyncio.create_task(
                self._run_agent(task, agent_cfg, tools)
            )
            for agent_cfg in agents[:self.max_parallel]
        ]
        
        # Run all agents simultaneously
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(f"ParallelRunner timeout after {self.timeout_seconds}s")
            results = [TimeoutError(f"Timeout after {self.timeout_seconds}s")] * len(tasks)
        
        # Convert to AgentResult objects
        agent_results = []
        for i, (result, cfg) in enumerate(zip(results, agents[:self.max_parallel])):
            if isinstance(result, Exception):
                agent_results.append(AgentResult(
                    role=cfg.get("role", f"agent_{i}"),
                    output=f"Error: {str(result)}",
                    confidence=0.0,
                    error=str(result),
                ))
            elif isinstance(result, AgentResult):
                agent_results.append(result)
            else:
                agent_results.append(AgentResult(
                    role=cfg.get("role", f"agent_{i}"),
                    output=str(result) if result else "No output",
                    confidence=0.5,
                ))
        
        # Converge results
        converged, winner = await self._converge(
            agent_results, task, converge_via
        )
        
        elapsed = (datetime.now() - t_start).total_seconds() * 1000
        
        logger.info(
            f"ParallelRunner: {len(agent_results)} agents, "
            f"converged via {converge_via} in {elapsed:.0f}ms"
        )
        
        return ParallelResult(
            agent_results=agent_results,
            converged_output=converged,
            convergence_method=converge_via,
            total_time_ms=elapsed,
            winner=winner,
        )
    
    async def _run_agent(
        self,
        task: str,
        agent_cfg: dict,
        tools: Optional[ToolRegistry],
    ) -> AgentResult:
        """Run one agent in the parallel group."""
        role = agent_cfg.get("role", "agent")
        system_prompt = agent_cfg.get("system", "You are a helpful assistant.")
        model = agent_cfg.get("model") or self.provider.get_default_model()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]
        
        tool_defs = tools.get_definitions() if tools else []
        tools_used = []
        iterations = 0
        max_iter = 10
        
        try:
            while iterations < max_iter:
                iterations += 1
                
                response = await self.provider.chat(
                    messages=messages,
                    tools=tool_defs,
                    model=model,
                )
                
                if response.has_tool_calls:
                    # Execute tools (simplified — no full loop)
                    for tc in response.tool_calls:
                        tools_used.append(tc.name)
                        # Tool execution would go here
                    messages.append({
                        "role": "assistant",
                        "content": response.content,
                        "tool_calls": [...],  # Simplified
                    })
                    messages.append({
                        "role": "tool",
                        "content": "Tool executed",
                    })
                else:
                    # No tool calls — done
                    return AgentResult(
                        role=role,
                        output=response.content or "",
                        confidence=self._extract_confidence(response.content),
                        tools_used=tools_used,
                        iterations=iterations,
                    )
            
            # Max iterations reached
            return AgentResult(
                role=role,
                output=messages[-1].get("content", ""),
                confidence=0.5,
                tools_used=tools_used,
                iterations=iterations,
            )
            
        except Exception as e:
            return AgentResult(
                role=role,
                output=f"Error: {str(e)}",
                confidence=0.0,
                error=str(e),
            )
    
    async def _converge(
        self,
        results: list[AgentResult],
        task: str,
        method: str,
    ) -> tuple[str, Optional[str]]:
        """Converge multiple agent results into one answer."""
        if method == "arbitration" and self.brier_scorer:
            return await self._arbitrate(results, task)
        elif method == "voting":
            return self._vote(results), None
        elif method == "llm_summary":
            return await self._llm_summarize(results, task), None
        else:
            # Default: return first result
            return results[0].output if results else "No results", None
    
    async def _arbitrate(
        self,
        results: list[AgentResult],
        task: str,
    ) -> tuple[str, Optional[str]]:
        """Use StrategyArbitrator (Brier-based) to pick the best result."""
        valid = [r for r in results if r.output and not r.error]
        if not valid:
            return "All agents failed.", None

        # Try full StrategyArbitrator first
        try:
            from jagabot.swarm.arbitrator import StrategyArbitrator
            arbitrator = StrategyArbitrator(brier_scorer=self.brier_scorer)
            perspectives = [
                {
                    "perspective": r.role,
                    "verdict":     r.output[:300],
                    "confidence":  r.confidence,
                    "evidence":    r.output[:100],
                }
                for r in valid
            ]
            arb_result = arbitrator.arbitrate_perspectives(
                perspectives=perspectives,
                domain="general",
            )
            winner_role   = arb_result.winner.perspective
            winner_output = next(
                (r.output for r in valid if r.role == winner_role),
                valid[0].output
            )
            method = arb_result.method
            gap    = arb_result.confidence_gap
            contested = "⚠️ Contested" if arb_result.was_contested else "✅ Clear"

            # Log rich arbitration result
            logger.info(
                f"Arbitration: {winner_role} wins "
                f"({contested}, gap={gap:.2f}, method={method})"
            )
            return winner_output, winner_role

        except Exception as _arb_err:
            logger.warning(f"StrategyArbitrator failed: {_arb_err} — falling back to voting")
            return self._vote(valid), valid[0].role if valid else None
    
    def _vote(self, results: list[AgentResult]) -> str:
        """Simple majority voting."""
        if not results:
            return "No results"
        
        # Count outputs (simplified — just pick most common first 50 chars)
        output_counts = {}
        for r in results:
            key = r.output[:50] if r.output else ""
            output_counts[key] = output_counts.get(key, 0) + 1
        
        if output_counts:
            most_common = max(output_counts.items(), key=lambda x: x[1])
            return most_common[0] + "..."
        
        return results[0].output if results else "No results"
    
    async def _llm_summarize(
        self,
        results: list[AgentResult],
        task: str,
    ) -> str:
        """Use LLM to summarize all outputs."""
        outputs = "\n\n".join(
            f"### {r.role}\n{r.output[:500]}"
            for r in results
        )
        
        prompt = f"""Task: {task}

Agent Outputs:
{outputs}

Provide a concise summary that synthesizes all perspectives."""
        
        try:
            response = await self.provider.chat(
                messages=[
                    {"role": "system", "content": "You are a synthesis engine."},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.content or "Summary failed"
        except Exception as e:
            return f"Summarization error: {e}"
    
    def _extract_confidence(self, content: str) -> float:
        """Extract confidence from output text."""
        if not content:
            return 0.5
        
        # Look for confidence indicators
        import re
        pct_match = re.search(r'(\d{1,3})%', content)
        if pct_match:
            return int(pct_match.group(1)) / 100
        
        # Look for confidence words
        high_conf = ["certain", "definitely", "clearly", "obviously"]
        low_conf = ["uncertain", "possibly", "might", "perhaps", "unsure"]
        
        content_lower = content.lower()
        if any(w in content_lower for w in high_conf):
            return 0.8
        if any(w in content_lower for w in low_conf):
            return 0.3
        
        return 0.5
