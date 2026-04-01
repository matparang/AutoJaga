"""Base channel interface."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Awaitable


class Channel(ABC):
    """
    Abstract base class for chat channels.
    
    Channels handle the interface between users and the chatbot,
    managing message input/output for different platforms.
    """
    
    def __init__(self, name: str):
        self.name = name
        self._message_handler: Callable[[str, str], Awaitable[str]] | None = None
    
    def set_message_handler(
        self, 
        handler: Callable[[str, str], Awaitable[str]]
    ) -> None:
        """
        Set the message handler callback.
        
        Args:
            handler: Async function that takes (user_id, message) and returns response.
        """
        self._message_handler = handler
    
    @abstractmethod
    async def start(self) -> None:
        """Start the channel (connect, listen for messages)."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel (disconnect, cleanup)."""
        pass
    
    @abstractmethod
    async def send(self, user_id: str, message: str) -> None:
        """
        Send a message to a user.
        
        Args:
            user_id: The recipient's ID.
            message: The message content.
        """
        pass
    
    async def handle_message(self, user_id: str, message: str) -> str:
        """
        Handle an incoming message.
        
        Args:
            user_id: The sender's ID.
            message: The message content.
        
        Returns:
            The response to send back.
        """
        if self._message_handler:
            return await self._message_handler(user_id, message)
        return "No message handler configured."
