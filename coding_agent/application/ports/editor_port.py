"""Abstract editor interface for applying code edits."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Tuple

from coding_agent.domain.models import Edit, EditResult


class EditorPort(ABC):
    """Abstract interface for code editors."""

    @abstractmethod
    async def apply_edit(self, edit: Edit) -> EditResult:
        """Apply a single edit.

        Args:
            edit: Edit to apply

        Returns:
            Result of the edit operation

        Raises:
            EditError: If edit cannot be applied
        """
        raise NotImplementedError

    @abstractmethod
    async def apply_edits(self, edits: List[Edit]) -> List[EditResult]:
        """Apply multiple edits.

        Args:
            edits: List of edits to apply

        Returns:
            List of edit results
        """
        raise NotImplementedError

    @abstractmethod
    async def validate_edit(self, edit: Edit, file_content: str) -> Tuple[bool, str]:
        """Validate that an edit can be applied.

        Args:
            edit: Edit to validate
            file_content: Current file content

        Returns:
            Tuple of (is_valid, error_message)
        """
        raise NotImplementedError

    @abstractmethod
    def supports_format(self, format_name: str) -> bool:
        """Check if editor supports a specific format.

        Args:
            format_name: Name of the format

        Returns:
            True if supported, False otherwise
        """
        raise NotImplementedError
