"""Custom exceptions for the coding agent."""

from pathlib import Path
from typing import Any, Optional


class CodingAgentError(Exception):
    """Base exception for all coding agent errors."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class LLMError(CodingAgentError):
    """Errors related to LLM communication."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class EditError(CodingAgentError):
    """Errors related to applying code edits."""

    def __init__(
        self,
        message: str,
        file_path: Optional[Path] = None,
        original_error: Optional[Exception] = None,
        search_text: Optional[str] = None,
    ):
        super().__init__(message)
        self.file_path = file_path
        self.original_error = original_error
        self.search_text = search_text


class ValidationError(CodingAgentError):
    """Errors related to validation."""

    def __init__(
        self,
        message: str,
        file_path: Optional[Path] = None,
        line_number: Optional[int] = None,
        column: Optional[int] = None,
    ):
        super().__init__(message)
        self.file_path = file_path
        self.line_number = line_number
        self.column = column


class ConfigurationError(CodingAgentError):
    """Errors related to configuration."""

    def __init__(self, message: str, config_key: Optional[str] = None):
        super().__init__(message)
        self.config_key = config_key


class ContextError(CodingAgentError):
    """Errors related to context building."""

    pass


class FileError(CodingAgentError):
    """Errors related to file operations."""

    def __init__(
        self,
        message: str,
        file_path: Optional[Path] = None,
        operation: Optional[str] = None,
    ):
        super().__init__(message)
        self.file_path = file_path
        self.operation = operation


class ParseError(CodingAgentError):
    """Errors related to parsing."""

    def __init__(
        self,
        message: str,
        file_path: Optional[Path] = None,
        parser_type: Optional[str] = None,
    ):
        super().__init__(message)
        self.file_path = file_path
        self.parser_type = parser_type
