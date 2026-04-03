"""Response DTOs."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from coding_agent.domain.models import EditResult


@dataclass
class CodingResponse:
    """Response from coding service."""

    message: str
    edit_results: List[EditResult] = field(default_factory=list)
    context_used: Optional[str] = None
    model: Optional[str] = None
    usage: Optional[Dict[str, int]] = None

    @property
    def has_edits(self) -> bool:
        """Check if any edits were applied."""
        return len(self.edit_results) > 0

    @property
    def successful_edits(self) -> List[EditResult]:
        """Get only successful edits."""
        return [e for e in self.edit_results if e.success]

    @property
    def failed_edits(self) -> List[EditResult]:
        """Get failed edits."""
        return [e for e in self.edit_results if not e.success]


@dataclass
class ContextResponse:
    """Response from context service."""

    context: str
    files_analyzed: List[Path] = field(default_factory=list)
    symbols_found: Dict[Path, List[str]] = field(default_factory=dict)
    token_count: int = 0
    truncated: bool = False

    @property
    def file_count(self) -> int:
        """Number of files analyzed."""
        return len(self.files_analyzed)
