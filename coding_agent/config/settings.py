"""Application settings using Pydantic."""

from pathlib import Path
from typing import List, Set

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM provider settings."""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    model: str = Field(default="gpt-4o", description="LLM model to use")
    api_key: SecretStr = Field(description="API key for the LLM provider")
    temperature: float = Field(default=0.1, ge=0, le=2, description="Sampling temperature")
    max_tokens: int = Field(default=2000, gt=0, description="Maximum tokens in response")
    timeout: float = Field(default=30.0, gt=0, description="Request timeout in seconds")
    provider: str = Field(default="openai", description="LLM provider (openai, anthropic, etc.)")


class ContextSettings(BaseSettings):
    """Context building settings."""

    model_config = SettingsConfigDict(env_prefix="CONTEXT_")

    token_budget: int = Field(default=1024, gt=0, description="Maximum tokens for context")
    max_files_auto: int = Field(
        default=10, gt=0, description="Max files to auto-scan when none specified"
    )
    map_multiplier_no_files: int = Field(
        default=8, gt=0, description="Multiplier for token budget when no files specified"
    )
    max_total_tokens: int = Field(
        default=32000, gt=0, description="Absolute maximum tokens"
    )
    token_estimation_ratio: float = Field(
        default=0.25, gt=0, description="Characters per token ratio (1/4)"
    )

    supported_extensions: Set[str] = Field(
        default_factory=lambda: {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".html",
            ".css",
            ".java",
            ".cpp",
            ".c",
            ".h",
            ".hpp",
            ".rs",
            ".go",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".scala",
            ".md",
            ".txt",
        }
    )

    ignore_patterns: Set[str] = Field(
        default_factory=lambda: {
            "__pycache__",
            ".git",
            ".svn",
            ".hg",
            ".pyc",
            ".log",
            ".pytest_cache",
            ".mypy_cache",
            ".tox",
            "node_modules",
            "__snapshots__",
        }
    )


class EditorSettings(BaseSettings):
    """Editor settings."""

    model_config = SettingsConfigDict(env_prefix="EDITOR_")

    backup_enabled: bool = Field(default=True, description="Create backups before editing")
    validate_syntax: bool = Field(default=True, description="Validate syntax after edits")
    auto_restore_on_failure: bool = Field(
        default=True, description="Auto-restore from backup on edit failure"
    )
    default_format: str = Field(default="search_replace", description="Default edit format")


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    debug: bool = Field(default=False, description="Enable debug mode")
    root_path: Path = Field(default=Path("."), description="Repository root path")

    llm: LLMSettings = Field(default_factory=LLMSettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    editor: EditorSettings = Field(default_factory=EditorSettings)

    @field_validator("root_path")
    @classmethod
    def validate_root_path(cls, v: Path) -> Path:
        """Validate root path exists."""
        if not v.exists():
            raise ValueError(f"Root path does not exist: {v}")
        return v.expanduser().resolve()

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count from text."""
        return int(len(text) * self.context.token_estimation_ratio)
