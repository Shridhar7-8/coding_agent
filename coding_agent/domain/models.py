"""Domain models - Core business entities."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class SymbolType(Enum):
    """Types of code symbols."""

    FUNCTION = auto()
    CLASS = auto()
    VARIABLE = auto()
    METHOD = auto()
    INTERFACE = auto()
    MODULE = auto()


class OperationType(Enum):
    """Types of edit operations."""

    SEARCH_REPLACE = auto()
    UNIFIED_DIFF = auto()
    CREATE_FILE = auto()
    DELETE_FILE = auto()


class ValidationStatus(Enum):
    """Validation result statuses."""

    PENDING = auto()
    VALID = auto()
    INVALID = auto()
    WARNING = auto()


@dataclass(frozen=True)
class Symbol:
    """Represents a code symbol (function, class, variable, etc.)."""

    name: str
    line: int
    symbol_type: SymbolType
    signature: Optional[str] = None
    file_path: Optional[Path] = None
    parent: Optional[str] = None
    methods: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict, hash=False)

    def __repr__(self) -> str:
        return f"Symbol({self.name}, {self.symbol_type.name}, line={self.line})"


@dataclass
class FileInfo:
    """Information about a source file."""

    path: Path
    language: Optional[str] = None
    size_bytes: int = 0
    last_modified: Optional[datetime] = None
    symbols: List[Symbol] = field(default_factory=list)
    dependencies: Set[str] = field(default_factory=set)

    @property
    def extension(self) -> str:
        """Get file extension."""
        return self.path.suffix


@dataclass
class Repository:
    """Repository information."""

    root_path: Path
    files: List[FileInfo] = field(default_factory=list)
    total_files: int = 0
    languages: Set[str] = field(default_factory=set)

    def get_files_by_language(self, language: str) -> List[FileInfo]:
        """Get all files of a specific language."""
        return [f for f in self.files if f.language == language]


@dataclass
class ValidationResult:
    """Result of validating an edit or file."""

    status: ValidationStatus
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    file_path: Optional[Path] = None

    @classmethod
    def valid(cls, file_path: Optional[Path] = None) -> "ValidationResult":
        """Create a valid result."""
        return cls(status=ValidationStatus.VALID, file_path=file_path)

    @classmethod
    def invalid(cls, errors: List[str], file_path: Optional[Path] = None) -> "ValidationResult":
        """Create an invalid result."""
        return cls(status=ValidationStatus.INVALID, errors=errors, file_path=file_path)

    @property
    def is_valid(self) -> bool:
        """Check if validation passed."""
        return self.status == ValidationStatus.VALID and not self.errors


@dataclass
class Edit:
    """Represents a code edit operation."""

    file_path: Path
    operation: OperationType
    search: Optional[str] = None
    replace: Optional[str] = None
    diff_content: Optional[str] = None
    line_number: Optional[int] = None
    validation_result: Optional[ValidationResult] = None

    def __post_init__(self):
        """Validate edit after creation."""
        if self.operation == OperationType.SEARCH_REPLACE:
            if self.search is None:
                raise ValueError("SEARCH_REPLACE operation requires 'search' content")


@dataclass(frozen=True)
class Message:
    """LLM message."""

    role: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict, hash=False)


@dataclass
class Response:
    """LLM response."""

    content: str
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    finish_reason: Optional[str] = None

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


@dataclass
class EditResult:
    """Result of applying an edit."""

    edit: Edit
    success: bool
    file_path: Path
    error_message: Optional[str] = None
    validation_result: Optional[ValidationResult] = None
    applied_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def success_result(cls, edit: Edit, file_path: Path) -> "EditResult":
        """Create a successful result."""
        return cls(
            edit=edit,
            success=True,
            file_path=file_path,
            validation_result=ValidationResult.valid(file_path),
        )

    @classmethod
    def failure_result(
        cls,
        edit: Edit,
        file_path: Path,
        error_message: str,
    ) -> "EditResult":
        """Create a failed result."""
        return cls(
            edit=edit,
            success=False,
            file_path=file_path,
            error_message=error_message,
            validation_result=ValidationResult.invalid([error_message], file_path),
        )
