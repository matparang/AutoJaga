"""Message bus module for decoupled channel-agent communication."""

from jagabot.bus.events import InboundMessage, OutboundMessage
from jagabot.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
