"""AutoJaga-Base — DeepMind Level 3 Autonomous Multi-Agent System.

A full agentic framework with:
- Everything in JagaRAG (conversation, memory, RAG)
- Tool binding and execution
- BDI (Belief-Desire-Intention) reasoning
- Multi-agent swarm orchestration
- Anti-fabrication harness
"""

__version__ = "1.0.0"
__author__ = "matparang"

from autojaga.agent.loop import AgentLoop

__all__ = ["AgentLoop", "__version__"]
