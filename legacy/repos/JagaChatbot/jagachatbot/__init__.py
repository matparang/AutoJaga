"""JagaChatbot — DeepMind Level 1 Conversational Agent.

A minimal, clean chatbot with:
- Multi-provider LLM routing (OpenAI, Anthropic, DeepSeek)
- Conversation memory and compression
- CLI and Telegram interfaces
"""

__version__ = "1.0.0"
__author__ = "matparang"

from jagachatbot.agent.loop import ChatLoop

__all__ = ["ChatLoop", "__version__"]
