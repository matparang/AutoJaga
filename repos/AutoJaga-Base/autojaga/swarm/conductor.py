"""
Swarm Orchestration — Multi-agent coordination.

Provides:
- Conductor: Orchestrates multiple specialist agents
- Specialist: Focused agent with specific expertise
- Synthesis: Combines outputs from multiple agents
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autojaga.providers.base import LLMProvider, LLMResponse


@dataclass
class SpecialistConfig:
    """Configuration for a specialist agent."""
    name: str
    role: str
    persona: str
    tools: list[str] = field(default_factory=list)
    model: str | None = None


@dataclass
class SwarmResult:
    """Result from a swarm execution."""
    query: str
    specialists: list[dict[str, Any]]
    synthesis: str
    total_time: float


class Specialist:
    """
    A specialist agent with focused expertise.
    
    Each specialist has a persona and set of tools optimized
    for their domain.
    """
    
    def __init__(
        self,
        config: SpecialistConfig,
        provider: LLMProvider,
        workspace: Path,
    ):
        self.config = config
        self.provider = provider
        self.workspace = workspace
    
    def _build_prompt(self, task: str) -> str:
        """Build specialist-specific prompt."""
        return f"""# {self.config.name}

You are {self.config.name}, a specialist agent with the following role:

**Role:** {self.config.role}

**Persona:** {self.config.persona}

**Available Tools:** {', '.join(self.config.tools) if self.config.tools else 'None'}

## Your Task

{task}

## Instructions

1. Focus on your area of expertise
2. Be thorough but concise
3. Cite sources when using external information
4. Provide your specialized perspective

Provide your expert analysis:"""
    
    async def execute(self, task: str) -> dict[str, Any]:
        """Execute the specialist's task."""
        import time
        start = time.time()
        
        prompt = self._build_prompt(task)
        
        response = await self.provider.chat(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": task},
            ],
            model=self.config.model,
        )
        
        elapsed = time.time() - start
        
        return {
            "name": self.config.name,
            "role": self.config.role,
            "response": response.content or "",
            "elapsed": round(elapsed, 2),
        }


class Conductor:
    """
    Orchestrates multiple specialist agents.
    
    The conductor:
    1. Receives a high-level query
    2. Dispatches to relevant specialists
    3. Synthesizes their outputs
    4. Returns unified response
    """
    
    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        specialists: list[SpecialistConfig] | None = None,
        model: str | None = None,
    ):
        self.provider = provider
        self.workspace = workspace
        self.model = model
        
        # Default specialists if none provided
        self.specialist_configs = specialists or self._default_specialists()
    
    def _default_specialists(self) -> list[SpecialistConfig]:
        """Default Mangliwood research swarm."""
        return [
            SpecialistConfig(
                name="Botanist",
                role="Plant Biology Expert",
                persona="Focused on Styrax taxonomy, morphology, and ecology",
                tools=["web_search", "read_file"],
            ),
            SpecialistConfig(
                name="Chemist",
                role="Natural Products Chemist",
                persona="Expert in secondary metabolites and compound analysis",
                tools=["web_search", "read_file"],
            ),
            SpecialistConfig(
                name="Pharmacologist",
                role="Drug Discovery Specialist",
                persona="Focused on therapeutic potential and bioactivity",
                tools=["web_search"],
            ),
        ]
    
    async def execute(self, query: str) -> SwarmResult:
        """
        Execute the swarm for a query.
        
        Args:
            query: The research query.
        
        Returns:
            SwarmResult with all specialist outputs and synthesis.
        """
        import time
        start = time.time()
        
        # Create specialists
        specialists = [
            Specialist(config, self.provider, self.workspace)
            for config in self.specialist_configs
        ]
        
        # Execute all specialists in parallel
        tasks = [s.execute(query) for s in specialists]
        results = await asyncio.gather(*tasks)
        
        # Synthesize results
        synthesis = await self._synthesize(query, results)
        
        total_time = time.time() - start
        
        return SwarmResult(
            query=query,
            specialists=results,
            synthesis=synthesis,
            total_time=round(total_time, 2),
        )
    
    async def _synthesize(
        self,
        query: str,
        specialist_results: list[dict[str, Any]],
    ) -> str:
        """Synthesize specialist outputs into unified response."""
        
        # Build synthesis prompt
        specialist_sections = []
        for result in specialist_results:
            specialist_sections.append(
                f"### {result['name']} ({result['role']})\n{result['response']}"
            )
        
        prompt = f"""# Synthesis Task

You are the Conductor agent, responsible for synthesizing multiple specialist perspectives into a coherent response.

## Original Query
{query}

## Specialist Responses

{chr(10).join(specialist_sections)}

## Your Task

Synthesize these specialist perspectives into a unified, coherent response that:
1. Integrates insights from all specialists
2. Resolves any contradictions
3. Highlights key findings
4. Provides actionable conclusions

Provide your synthesis:"""
        
        response = await self.provider.chat(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Synthesize the specialist responses."},
            ],
            model=self.model,
        )
        
        return response.content or ""


def create_mangliwood_swarm(
    provider: LLMProvider,
    workspace: Path,
) -> Conductor:
    """Create the demo Mangliwood research swarm."""
    specialists = [
        SpecialistConfig(
            name="Botanist",
            role="Styrax Biology Expert",
            persona=(
                "Expert in Mangliwood (Styrax) taxonomy and ecology. "
                "Deep knowledge of Southeast Asian rainforest flora."
            ),
            tools=["web_search", "read_file"],
        ),
        SpecialistConfig(
            name="Materials Scientist",
            role="Resin Properties Expert",
            persona=(
                "Specialist in natural resins and their material properties. "
                "Knowledge of traditional and modern extraction methods."
            ),
            tools=["web_search", "read_file"],
        ),
        SpecialistConfig(
            name="Chemist",
            role="Benzoin Compound Analyst",
            persona=(
                "Natural products chemist focused on cinnamic acid derivatives, "
                "benzoin compounds, and antimicrobial activity."
            ),
            tools=["web_search"],
        ),
        SpecialistConfig(
            name="Pathologist",
            role="Antimicrobial Research",
            persona=(
                "Infectious disease researcher interested in natural antimicrobials "
                "and their mechanisms of action."
            ),
            tools=["web_search"],
        ),
        SpecialistConfig(
            name="Synthesizer",
            role="Research Integration",
            persona=(
                "Cross-disciplinary researcher who connects botanical, chemical, "
                "and medical perspectives into actionable insights."
            ),
            tools=["read_file", "write_file"],
        ),
    ]
    
    return Conductor(
        provider=provider,
        workspace=workspace,
        specialists=specialists,
    )
