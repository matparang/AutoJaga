"""UpsonicChatAgent — memory-backed multi-turn chat via Upsonic Agent framework.

Wraps Upsonic's Agent + Memory (InMemoryStorage) with financial safety policies.
Gracefully degrades when upsonic is not installed.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Optional

try:
    from upsonic import Agent, Task
    from upsonic.storage.in_memory import InMemoryStorage
    from upsonic.storage.memory import Memory

    _UPSONIC_AVAILABLE = True
except ImportError:  # pragma: no cover
    _UPSONIC_AVAILABLE = False
    Agent = None  # type: ignore[assignment,misc]
    Task = None  # type: ignore[assignment,misc]
    InMemoryStorage = None  # type: ignore[assignment,misc]
    Memory = None  # type: ignore[assignment,misc]

try:
    from upsonic.safety_engine.policies.pii_policies import AnonymizeEmailPolicy

    _SAFETY_AVAILABLE = True
except Exception:  # pragma: no cover
    _SAFETY_AVAILABLE = False
    AnonymizeEmailPolicy = None  # type: ignore[assignment,misc]


# Registry of active sessions: session_id → UpsonicChatAgent
_session_registry: dict[str, "UpsonicChatAgent"] = {}


class UpsonicChatAgentError(RuntimeError):
    """Raised when Upsonic is not installed or agent initialisation fails."""


class UpsonicChatAgent:
    """Memory-backed conversational agent powered by Upsonic.

    Each instance maintains its own session memory so multi-turn conversations
    retain context across calls.

    Usage::

        agent = UpsonicChatAgent.get_or_create("session-abc")
        result = await agent.chat_async("Analyze my VIX 55 oil portfolio")
        result2 = await agent.chat_async("What if VIX goes to 65?")
        # result2 will know about the oil portfolio from the first turn
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        model: str = "openai/gpt-4o",
        name: str = "JAGABOT Assistant",
        apply_safety: bool = True,
    ) -> None:
        if not _UPSONIC_AVAILABLE:
            raise UpsonicChatAgentError(
                "Upsonic is not installed. Run: pip install -e Upsonic/"
            )

        self.session_id = session_id or uuid.uuid4().hex
        self.model = model
        self.name = name

        storage = InMemoryStorage()
        self.memory = Memory(
            storage=storage,
            session_id=self.session_id,
            full_session_memory=True,
        )

        # Financial / PII safety policies
        user_policy = None
        if apply_safety and _SAFETY_AVAILABLE and AnonymizeEmailPolicy is not None:
            try:
                user_policy = AnonymizeEmailPolicy()
            except Exception:
                user_policy = None

        self.agent = Agent(
            model=model,
            memory=self.memory,
            name=name,
            user_policy=user_policy,
            debug=False,
        )

        self._message_count: int = 0

    # ------------------------------------------------------------------
    # Session registry helpers
    # ------------------------------------------------------------------

    @classmethod
    def get_or_create(
        cls,
        session_id: str,
        model: str = "openai/gpt-4o",
        **kwargs,
    ) -> "UpsonicChatAgent":
        """Return existing agent for session_id or create a new one."""
        if session_id not in _session_registry:
            _session_registry[session_id] = cls(session_id=session_id, model=model, **kwargs)
        return _session_registry[session_id]

    @classmethod
    def active_sessions(cls) -> list[str]:
        """Return list of active session IDs."""
        return list(_session_registry.keys())

    @classmethod
    def clear_session(cls, session_id: str) -> bool:
        """Remove session from registry. Returns True if it existed."""
        return _session_registry.pop(session_id, None) is not None

    # ------------------------------------------------------------------
    # Core chat interface
    # ------------------------------------------------------------------

    async def chat_async(self, message: str) -> str:
        """Send a message and return the agent's response (async).

        Conversation history is preserved in Memory across calls.
        """
        if not _UPSONIC_AVAILABLE:
            raise UpsonicChatAgentError("Upsonic not installed")

        task = Task(description=message)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self.agent.do, task)
        self._message_count += 1
        return str(result) if result is not None else ""

    def chat(self, message: str) -> str:
        """Synchronous wrapper around chat_async."""
        return asyncio.run(self.chat_async(message))

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """Return session statistics."""
        return {
            "session_id": self.session_id,
            "model": self.model,
            "message_count": self._message_count,
            "upsonic_available": _UPSONIC_AVAILABLE,
            "safety_available": _SAFETY_AVAILABLE,
        }

    def __repr__(self) -> str:
        return (
            f"UpsonicChatAgent(session_id={self.session_id!r}, "
            f"model={self.model!r}, messages={self._message_count})"
        )
