"""
TelegramThinkingManager

Sends and edits a "Thinking..." message in Telegram as the agent
works, showing real-time reasoning steps.

Flow:
  User sends message
  → Bot sends: "🧠 Thinking..."
  → Tool starts: edits to "🧠 Thinking...\n  📈 Getting NVDA price..."
  → Tool done: edits to "🧠 Thinking...\n  📈 Getting NVDA price... ✅ $178.56"
  → Response ready: deletes thinking message, sends final answer

Handles:
  - Message edit rate limits (Telegram: max 1 edit/second)
  - Edit failures (fallback to new message)
  - Long messages (truncate to 4096 chars)
"""

from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from loguru import logger

MAX_MSG_LEN   = 4000   # Telegram limit is 4096
EDIT_INTERVAL = 1.2    # seconds between edits (rate limit buffer)


@dataclass
class ThinkingState:
    """State for one thinking session."""
    chat_id:    int
    message_id: int
    steps:      list[str] = field(default_factory=list)
    last_edit:  float     = 0.0
    active:     bool      = True


class TelegramThinkingManager:
    """
    Manages "thinking" message lifecycle for Telegram.
    One instance per Telegram channel handler.
    """

    def __init__(self, bot):
        self._bot   = bot
        self._states: dict[int, ThinkingState] = {}  # chat_id → state

    async def start(self, chat_id: int, query: str, complexity: str = "STANDARD") -> int | None:
        """
        Send initial thinking message. Returns message_id or None.
        """
        icon = "🔬" if complexity == "RESEARCH" else "💭" if complexity == "COMPLEX" else "⚡"
        text = f"{icon} *Thinking...*\n`{query[:60]}{'...' if len(query) > 60 else ''}`"

        try:
            msg = await self._bot.send_message(
                chat_id    = chat_id,
                text       = text,
                parse_mode = "Markdown",
            )
            state = ThinkingState(chat_id=chat_id, message_id=msg.message_id)
            self._states[chat_id] = state
            logger.debug(f"TelegramThinking: started for chat {chat_id}, msg {msg.message_id}")
            return msg.message_id
        except Exception as e:
            logger.debug(f"TelegramThinking: start failed: {e}")
            return None

    async def add_step(self, chat_id: int, step: str) -> None:
        """Add a reasoning step and update the thinking message."""
        state = self._states.get(chat_id)
        if not state or not state.active:
            return

        state.steps.append(step)

        # Rate limit edits
        now = time.time()
        if now - state.last_edit < EDIT_INTERVAL:
            return  # Skip this edit to avoid rate limit

        await self._do_edit(state)

    async def _do_edit(self, state: ThinkingState) -> None:
        """Actually edit the Telegram message."""
        if not state.steps:
            return

        lines = ["🧠 *Thinking...*"]
        for step in state.steps[-6:]:  # show last 6 steps only
            lines.append(f"  {step}")

        text = "\n".join(lines)
        if len(text) > MAX_MSG_LEN:
            text = text[:MAX_MSG_LEN] + "..."

        try:
            await self._bot.edit_message_text(
                chat_id    = state.chat_id,
                message_id = state.message_id,
                text       = text,
                parse_mode = "Markdown",
            )
            state.last_edit = time.time()
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.debug(f"TelegramThinking: edit failed: {e}")

    async def finish(self, chat_id: int, delete: bool = True) -> None:
        """
        Finish thinking session.
        If delete=True, removes the thinking message.
        If delete=False, updates with final step summary.
        """
        state = self._states.get(chat_id)
        if not state:
            return

        state.active = False

        if delete:
            try:
                await self._bot.delete_message(
                    chat_id    = state.chat_id,
                    message_id = state.message_id,
                )
                logger.debug(f"TelegramThinking: deleted for chat {chat_id}")
            except Exception as e:
                logger.debug(f"TelegramThinking: delete failed: {e}")
        else:
            # Update with completion summary
            count = len(state.steps)
            await self._do_edit_text(
                state,
                f"✅ *Done* ({count} step{'s' if count != 1 else ''})"
            )

        del self._states[chat_id]

    async def _do_edit_text(self, state: ThinkingState, text: str) -> None:
        """Edit message to specific text."""
        try:
            await self._bot.edit_message_text(
                chat_id    = state.chat_id,
                message_id = state.message_id,
                text       = text,
                parse_mode = "Markdown",
            )
        except Exception as e:
            logger.debug(f"TelegramThinking: edit_text failed: {e}")

    def get_state(self, chat_id: int) -> ThinkingState | None:
        return self._states.get(chat_id)
