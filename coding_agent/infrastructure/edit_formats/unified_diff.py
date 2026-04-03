"""Unified diff edit format implementation."""

import re
from pathlib import Path
from typing import List, Tuple

from coding_agent.application.ports.editor_port import EditorPort
from coding_agent.domain.models import Edit, EditResult, OperationType, ValidationResult
from coding_agent.utils.errors import EditError


class UnifiedDiffFormat(EditorPort):
    """Editor for unified diff format edits."""

    def __init__(self, root_path: Path = Path(".")):
        self._root = root_path

    async def apply_edit(self, edit: Edit) -> EditResult:
        """Apply a unified diff edit.

        Args:
            edit: Edit to apply

        Returns:
            Result of the operation
        """
        if edit.operation != OperationType.UNIFIED_DIFF:
            return EditResult.failure_result(
                edit=edit,
                file_path=edit.file_path,
                error_message=f"Expected UNIFIED_DIFF operation, got {edit.operation}",
            )

        if not edit.diff_content:
            return EditResult.failure_result(
                edit=edit,
                file_path=edit.file_path,
                error_message="Diff content is empty",
            )

        file_path = self._root / edit.file_path

        try:
            # Parse hunks from diff
            hunks = self._parse_hunks(edit.diff_content)

            # Read existing file or start empty
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            else:
                lines = []

            # Apply hunks in reverse order to preserve line numbers
            for hunk in reversed(hunks):
                lines = self._apply_hunk(lines, hunk)

            # Write result
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

            return EditResult.success_result(edit, edit.file_path)

        except Exception as e:
            raise EditError(
                f"Failed to apply diff: {e}",
                file_path=edit.file_path,
                original_error=e,
            )

    async def apply_edits(self, edits) -> list:
        """Apply multiple edits."""
        results = []
        for edit in edits:
            result = await self.apply_edit(edit)
            results.append(result)
        return results

    async def validate_edit(self, edit: Edit, file_content: str) -> Tuple[bool, str]:
        """Validate a diff can be applied.

        Args:
            edit: Edit to validate
            file_content: Current content

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not edit.diff_content:
            return False, "Diff content is empty"

        try:
            hunks = self._parse_hunks(edit.diff_content)
            lines = file_content.split("\n")

            for hunk in hunks:
                if not self._can_apply_hunk(lines, hunk):
                    return False, "Cannot apply hunk - context mismatch"

            return True, ""
        except Exception as e:
            return False, f"Invalid diff format: {e}"

    def supports_format(self, format_name: str) -> bool:
        """Check if format is supported.

        Args:
            format_name: Format name

        Returns:
            True if supported
        """
        return format_name == "udiff"

    def _parse_hunks(self, diff_content: str) -> List["Hunk"]:
        """Parse diff into hunks.

        Args:
            diff_content: Diff content

        Returns:
            List of hunks
        """
        hunks = []
        lines = diff_content.split("\n")
        current_hunk = None

        i = 0
        while i < len(lines):
            line = lines[i]

            # Skip header lines
            if line.startswith("---") or line.startswith("+++"):
                i += 1
                continue

            # Hunk header
            if line.startswith("@@"):
                # Parse hunk header: @@ -start,count +start,count @@
                match = re.match(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@", line)
                if match:
                    old_start = int(match.group(1))
                    old_count = int(match.group(2)) if match.group(2) else 1
                    new_start = int(match.group(3))
                    new_count = int(match.group(4)) if match.group(4) else 1

                    current_hunk = Hunk(
                        old_start=old_start,
                        old_count=old_count,
                        new_start=new_start,
                        new_count=new_count,
                        lines=[],
                    )
                    hunks.append(current_hunk)
                i += 1
                continue

            # Hunk content
            if current_hunk is not None and line:
                current_hunk.lines.append(line)

            i += 1

        return hunks

    def _apply_hunk(self, lines: List[str], hunk: "Hunk") -> List[str]:
        """Apply a hunk to lines.

        Args:
            lines: Current lines
            hunk: Hunk to apply

        Returns:
            Modified lines
        """
        # Convert to 0-indexed
        start = hunk.old_start - 1

        result = lines[:start]

        for line in hunk.lines:
            if line.startswith("-"):
                # Remove line - skip it
                continue
            elif line.startswith("+"):
                # Add line
                result.append(line[1:] + "\n")
            elif line.startswith(" "):
                # Context line - keep it
                result.append(line[1:] + "\n")
            else:
                # Regular line
                result.append(line + "\n")

        result.extend(lines[start + hunk.old_count :])
        return result

    def _can_apply_hunk(self, lines: List[str], hunk: "Hunk") -> bool:
        """Check if hunk can be applied.

        Args:
            lines: Current lines
            hunk: Hunk to check

        Returns:
            True if can apply
        """
        start = hunk.old_start - 1
        if start + hunk.old_count > len(lines):
            return False

        # Check context lines match
        for i, line in enumerate(hunk.lines):
            if line.startswith(" "):
                expected = line[1:]
                actual = lines[start + i].rstrip("\n")
                if expected != actual:
                    return False

        return True


class Hunk:
    """Represents a diff hunk."""

    def __init__(
        self,
        old_start: int,
        old_count: int,
        new_start: int,
        new_count: int,
        lines: List[str],
    ):
        self.old_start = old_start
        self.old_count = old_count
        self.new_start = new_start
        self.new_count = new_count
        self.lines = lines
