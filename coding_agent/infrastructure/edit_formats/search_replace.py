"""Search/REPLACE edit format implementation."""

import re
import textwrap
from pathlib import Path
from typing import Tuple

from coding_agent.application.ports.editor_port import EditorPort
from coding_agent.domain.models import Edit, EditResult, OperationType, ValidationResult
from coding_agent.utils.errors import EditError


class SearchReplaceFormat(EditorPort):
    """Editor for SEARCH/REPLACE format edits."""

    def __init__(self, root_path: Path = Path(".")):
        self._root = root_path

    async def apply_edit(self, edit: Edit) -> EditResult:
        """Apply a SEARCH/REPLACE edit.

        Args:
            edit: Edit to apply

        Returns:
            Result of the operation
        """
        if edit.operation != OperationType.SEARCH_REPLACE:
            return EditResult.failure_result(
                edit=edit,
                file_path=edit.file_path,
                error_message=f"Expected SEARCH_REPLACE operation, got {edit.operation}",
            )

        file_path = self._root / edit.file_path

        try:
            # Read file content
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except FileNotFoundError:
                return EditResult.failure_result(
                    edit=edit,
                    file_path=edit.file_path,
                    error_message=f"File not found: {edit.file_path}",
                )

            if edit.search is None:
                return EditResult.failure_result(
                    edit=edit,
                    file_path=edit.file_path,
                    error_message="Search content is None",
                )

            # Try exact match first
            if edit.search in content:
                new_content = content.replace(edit.search, edit.replace or "", 1)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                # Validate the result
                validation = await self._validate(file_path)

                return EditResult.success_result(edit, edit.file_path)

            # Try normalized whitespace match
            normalized_search = textwrap.dedent(edit.search).strip()
            content_lines = content.split("\n")
            search_lines = normalized_search.split("\n")

            for i in range(len(content_lines) - len(search_lines) + 1):
                segment = "\n".join(content_lines[i : i + len(search_lines)])
                segment_normalized = textwrap.dedent(segment).strip()

                if segment_normalized == normalized_search:
                    # Found match, apply replacement
                    new_lines = (
                        content_lines[:i]
                        + (edit.replace or "").split("\n")
                        + content_lines[i + len(search_lines) :]
                    )
                    new_content = "\n".join(new_lines)

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)

                    return EditResult.success_result(edit, edit.file_path)

            # No match found
            return EditResult.failure_result(
                edit=edit,
                file_path=edit.file_path,
                error_message="Search text not found in file",
            )

        except Exception as e:
            raise EditError(
                f"Failed to apply edit: {e}",
                file_path=edit.file_path,
                search_text=edit.search,
            )

    async def apply_edits(self, edits) -> list:
        """Apply multiple edits."""
        results = []
        for edit in edits:
            result = await self.apply_edit(edit)
            results.append(result)
        return results

    async def validate_edit(self, edit: Edit, file_content: str) -> Tuple[bool, str]:
        """Validate an edit can be applied.

        Args:
            edit: Edit to validate
            file_content: Current content

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not edit.search:
            return False, "Search content is empty"

        if edit.search in file_content:
            return True, ""

        # Try normalized match
        normalized_search = textwrap.dedent(edit.search).strip()
        normalized_content = textwrap.dedent(file_content).strip()

        if normalized_search in normalized_content:
            return True, ""

        return False, "Search text not found in file"

    def supports_format(self, format_name: str) -> bool:
        """Check if format is supported.

        Args:
            format_name: Format name

        Returns:
            True if supported
        """
        return format_name in ("search_replace", "diff")

    async def _validate(self, file_path: Path) -> ValidationResult:
        """Validate Python syntax if applicable.

        Args:
            file_path: Path to file

        Returns:
            Validation result
        """
        if file_path.suffix != ".py":
            return ValidationResult.valid(file_path)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            compile(content, str(file_path), "exec")
            return ValidationResult.valid(file_path)
        except SyntaxError as e:
            return ValidationResult.invalid(
                [f"Syntax error at line {e.lineno}: {e.msg}"],
                file_path,
            )
