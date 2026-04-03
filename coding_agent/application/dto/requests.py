"""Request DTOs."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class CodingRequest:
    """Request for coding assistance."""

    message: str
    files: List[Path] = field(default_factory=list)
    context: Optional[str] = None
    mentioned_symbols: Set[str] = field(default_factory=set)
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    edit_format: str = field(default="search_replace")

    def __post_init__(self):
        """Normalize file paths."""
        self.files = [Path(f) if isinstance(f, str) else f for f in self.files]


@dataclass
class ContextRequest:
    """Request for context building."""

    files: List[Path] = field(default_factory=list)
    query: str = ""
    mentioned_symbols: Set[str] = field(default_factory=set)
    max_tokens: Optional[int] = None

    def __post_init__(self):
        """Normalize file paths."""
        self.files = [Path(f) if isinstance(f, str) else f for f in self.files]
