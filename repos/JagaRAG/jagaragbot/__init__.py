"""JagaRAG — DeepMind Level 2 Retrieval-Augmented Agent.

A RAG-enhanced chatbot with:
- Everything in JagaChatbot (multi-provider LLM, memory, compression)
- Vector memory for semantic search
- Document ingestion pipeline
- Retrieval-grounded responses
"""

__version__ = "1.0.0"
__author__ = "matparang"

from jagaragbot.agent.loop import RAGLoop

__all__ = ["RAGLoop", "__version__"]
