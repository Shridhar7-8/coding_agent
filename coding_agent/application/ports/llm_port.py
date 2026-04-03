"""Abstract LLM provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    """Message for LLM communication."""

    role: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Response:
    """Response from LLM."""

    content: str
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    finish_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def contains_edits(self) -> bool:
        """Check if response contains edit instructions."""
        edit_indicators = [
            "<<<<<<< SEARCH",
            "```diff",
            "--- ",
            "+++ ",
            ">>>>>>> REPLACE",
        ]
        return any(indicator in self.content for indicator in edit_indicators)


class LLMPort(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def complete(self, messages: List[Message]) -> Response:
        """Send messages and get completion response.

        Args:
            messages: List of messages to send

        Returns:
            Response from the LLM

        Raises:
            LLMError: If the request fails
        """
        raise NotImplementedError

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the LLM service is available.

        Returns:
            True if healthy, False otherwise
        """
        raise NotImplementedError
