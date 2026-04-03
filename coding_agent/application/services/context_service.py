"""Context service for building repository context."""

import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from coding_agent.application.dto.requests import ContextRequest
from coding_agent.application.dto.responses import ContextResponse
from coding_agent.application.ports.file_storage_port import FileStoragePort
from coding_agent.application.ports.parser_port import ParserPort
from coding_agent.config.settings import ContextSettings
from coding_agent.domain.models import FileInfo, Repository, Symbol


@dataclass
class _ScoredFile:
    """Internal class for scoring file importance."""

    file_info: FileInfo
    score: float = 0.0

    def __lt__(self, other: "_ScoredFile") -> bool:
        return self.score < other.score


class ContextService:
    """Service for building optimized context for LLM interactions."""

    def __init__(
        self,
        file_storage: FileStoragePort,
        parser: ParserPort,
        settings: ContextSettings,
    ):
        self._file_storage = file_storage
        self._parser = parser
        self._settings = settings
        self._symbol_cache: Dict[Path, List[Symbol]] = {}
        self._content_cache: Dict[Path, Tuple[str, float]] = {}  # path -> (content, mtime)

    async def build(self, request: ContextRequest) -> ContextResponse:
        """Build context from files.

        Args:
            request: Context building request

        Returns:
            Context response with optimized context
        """
        # Scan repository if no files specified
        files = request.files
        if not files:
            files = await self._scan_repository()
            files = files[: self._settings.max_files_auto]

        # Get file info for all files
        file_infos = []
        for file_path in files:
            try:
                info = await self._file_storage.get_info(file_path)
                info.symbols = await self._get_symbols(file_path)
                file_infos.append(info)
            except Exception as e:
                # Log error but continue with other files
                continue

        if not file_infos:
            return ContextResponse(
                context="No files found to analyze.",
                files_analyzed=[],
            )

        # Score files by importance
        scored_files = await self._score_files(
            file_infos, request.mentioned_symbols
        )

        # Build context within token budget
        context_parts, analyzed_files, symbols_found = await self._build_context(
            scored_files, request.query
        )

        context_str = "".join(context_parts)
        token_count = int(len(context_str) / 4)  # Rough estimate

        return ContextResponse(
            context=context_str,
            files_analyzed=analyzed_files,
            symbols_found=symbols_found,
            token_count=token_count,
            truncated=len(analyzed_files) < len(scored_files),
        )

    async def _scan_repository(self) -> List[Path]:
        """Scan repository for source files.

        Returns:
            List of file paths
        """
        root = Path(".")
        files = []

        for dirpath, dirnames, filenames in os.walk(root):
            # Filter out ignored directories
            dirnames[:] = [
                d
                for d in dirnames
                if not d.startswith(".") and d not in self._settings.ignore_patterns
            ]

            for filename in filenames:
                if self._should_include_file(filename):
                    file_path = Path(dirpath) / filename
                    try:
                        rel_path = file_path.relative_to(root)
                        files.append(rel_path)
                    except ValueError:
                        files.append(file_path)

        return files

    def _should_include_file(self, filename: str) -> bool:
        """Check if file should be included.

        Args:
            filename: Name of file

        Returns:
            True if should include
        """
        path = Path(filename)
        return (
            path.suffix in self._settings.supported_extensions
            and not any(
                ignore in filename for ignore in self._settings.ignore_patterns
            )
        )

    async def _get_symbols(self, file_path: Path) -> List[Symbol]:
        """Get symbols for file with caching.

        Args:
            file_path: Path to file

        Returns:
            List of symbols
        """
        # Check if cache is valid
        try:
            current_mtime = await self._file_storage.get_modification_time(file_path)
            if file_path in self._symbol_cache:
                cached_mtime = self._content_cache.get(file_path, (None, 0))[1]
                if current_mtime.timestamp() <= cached_mtime:
                    return self._symbol_cache[file_path]
        except Exception:
            pass

        # Parse file
        try:
            symbols = await self._parser.parse(file_path)
            self._symbol_cache[file_path] = symbols
            try:
                mtime = await self._file_storage.get_modification_time(file_path)
                self._content_cache[file_path] = ("", mtime.timestamp())
            except Exception:
                pass
            return symbols
        except Exception:
            return []

    async def _score_files(
        self, file_infos: List[FileInfo], mentioned_symbols: Set[str]
    ) -> List[_ScoredFile]:
        """Score files by importance.

        Args:
            file_infos: List of file info
            mentioned_symbols: Symbols mentioned in query

        Returns:
            List of scored files, sorted by score
        """
        scored = []

        for file_info in file_infos:
            score = 1.0  # Base score

            # Boost for symbols mentioned in query
            for symbol in file_info.symbols:
                if symbol.name in mentioned_symbols:
                    score *= 10

                # Boost public symbols
                if not symbol.name.startswith("_"):
                    score *= 1.5

            scored.append(_ScoredFile(file_info=file_info, score=score))

        # Sort by score descending
        scored.sort(reverse=True)
        return scored

    async def _build_context(
        self, scored_files: List[_ScoredFile], query: str
    ) -> Tuple[List[str], List[Path], Dict[Path, List[str]]]:
        """Build context string from scored files.

        Args:
            scored_files: Files sorted by importance
            query: Original query

        Returns:
            Tuple of (context parts, analyzed files, symbols found)
        """
        context_parts = []
        analyzed_files = []
        symbols_found: Dict[Path, List[str]] = {}

        # Build repository overview
        languages = set()
        for sf in scored_files:
            if sf.file_info.language:
                languages.add(sf.file_info.language)

        overview = f"Repository: {len(scored_files)} files\n"
        overview += f"Languages: {', '.join(sorted(languages))}\n\n"
        context_parts.append(overview)

        current_tokens = len(overview) // 4

        # Add file contexts within token budget
        for scored_file in scored_files:
            if current_tokens >= self._settings.token_budget:
                break

            file_info = scored_file.file_info
            file_section = self._format_file_context(file_info)
            section_tokens = len(file_section) // 4

            if current_tokens + section_tokens <= self._settings.token_budget:
                context_parts.append(file_section)
                analyzed_files.append(file_info.path)
                symbols_found[file_info.path] = [
                    s.name for s in file_info.symbols[:10]
                ]
                current_tokens += section_tokens

        return context_parts, analyzed_files, symbols_found

    def _format_file_context(self, file_info: FileInfo) -> str:
        """Format file info as context string.

        Args:
            file_info: File information

        Returns:
            Formatted string
        """
        lines = [f"{file_info.path}:\n"]

        # Add classes with methods
        for symbol in file_info.symbols:
            if symbol.symbol_type.value == 2:  # CLASS
                lines.append(f"  class {symbol.name}:\n")
                for method in symbol.methods[:5]:
                    lines.append(f"    def {method}():\n")

        # Add functions
        for symbol in file_info.symbols:
            if symbol.symbol_type.value == 1:  # FUNCTION
                sig = symbol.signature or f"{symbol.name}()"
                lines.append(f"  def {sig}\n")

        # Add important variables
        for symbol in file_info.symbols:
            if symbol.symbol_type.value == 3:  # VARIABLE
                lines.append(f"  {symbol.name}\n")

        lines.append("\n")
        return "".join(lines)

    def clear_cache(self) -> None:
        """Clear symbol and content caches."""
        self._symbol_cache.clear()
        self._content_cache.clear()
