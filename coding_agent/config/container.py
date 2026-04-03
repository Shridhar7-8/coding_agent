"""Dependency injection container - simplified factory pattern."""

import os
from pathlib import Path
from typing import Dict

from coding_agent.config.settings import Settings
from coding_agent.infrastructure.llm.openai_provider import OpenAIClient
from coding_agent.infrastructure.parsers.multi_parser import MultiLanguageParser
from coding_agent.infrastructure.storage.file_storage import LocalFileStorage
from coding_agent.infrastructure.edit_formats.search_replace import SearchReplaceFormat
from coding_agent.infrastructure.edit_formats.unified_diff import UnifiedDiffFormat
from coding_agent.application.services.context_service import ContextService
from coding_agent.application.services.coding_service import CodingService


class Container:
    """Simple dependency injection container using factory pattern."""

    def __init__(self):
        self._settings: Settings = None
        self._file_storage: LocalFileStorage = None
        self._parser: MultiLanguageParser = None
        self._llm_client: OpenAIClient = None
        self._edit_formats: Dict = None
        self._context_service: ContextService = None
        self._coding_service: CodingService = None

    def init(self, settings: Settings) -> None:
        """Initialize container with settings."""
        self._settings = settings

    @property
    def settings(self) -> Settings:
        """Get settings."""
        if self._settings is None:
            self._settings = Settings()
        return self._settings

    @property
    def file_storage(self) -> LocalFileStorage:
        """Get file storage."""
        if self._file_storage is None:
            self._file_storage = LocalFileStorage(root_path=self.settings.root_path)
        return self._file_storage

    @property
    def parser(self) -> MultiLanguageParser:
        """Get parser."""
        if self._parser is None:
            self._parser = MultiLanguageParser()
        return self._parser

    @property
    def llm_client(self) -> OpenAIClient:
        """Get LLM client."""
        if self._llm_client is None:
            self._llm_client = OpenAIClient(
                api_key=self.settings.llm.api_key,
                model=self.settings.llm.model,
                temperature=self.settings.llm.temperature,
                max_tokens=self.settings.llm.max_tokens,
                timeout=self.settings.llm.timeout,
            )
        return self._llm_client

    @property
    def edit_formats(self) -> Dict:
        """Get edit format handlers."""
        if self._edit_formats is None:
            root = self.settings.root_path
            self._edit_formats = {
                "search_replace": SearchReplaceFormat(root_path=root),
                "diff": SearchReplaceFormat(root_path=root),
                "udiff": UnifiedDiffFormat(root_path=root),
            }
        return self._edit_formats

    @property
    def context_service(self) -> ContextService:
        """Get context service."""
        if self._context_service is None:
            self._context_service = ContextService(
                file_storage=self.file_storage,
                parser=self.parser,
                settings=self.settings.context,
            )
        return self._context_service

    @property
    def coding_service(self) -> CodingService:
        """Get coding service."""
        if self._coding_service is None:
            self._coding_service = CodingService(
                llm_client=self.llm_client,
                context_service=self.context_service,
                file_storage=self.file_storage,
                edit_formats=self.edit_formats,
                settings=self.settings,
            )
        return self._coding_service


# Global container instance
_container = Container()


def get_container() -> Container:
    """Get the global container instance."""
    return _container
