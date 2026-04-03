"""Abstract parser interface for symbol extraction."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional

from coding_agent.domain.models import Symbol, SymbolType


class ParserPort(ABC):
    """Abstract interface for code parsers."""

    @abstractmethod
    async def parse(self, file_path: Path, content: Optional[str] = None) -> List[Symbol]:
        """Parse file and extract symbols.

        Args:
            file_path: Path to file
            content: Optional pre-loaded content

        Returns:
            List of extracted symbols

        Raises:
            ParseError: If parsing fails
        """
        raise NotImplementedError

    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the file.

        Args:
            file_path: Path to file

        Returns:
            True if can parse, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def get_language(self, file_path: Path) -> Optional[str]:
        """Get language identifier for file.

        Args:
            file_path: Path to file

        Returns:
            Language identifier or None
        """
        raise NotImplementedError

    @abstractmethod
    async def find_references(
        self,
        symbol: Symbol,
        files: List[Path],
    ) -> Dict[Path, List[int]]:
        """Find references to a symbol in files.

        Args:
            symbol: Symbol to find references for
            files: Files to search

        Returns:
            Dictionary mapping file paths to line numbers
        """
        raise NotImplementedError
