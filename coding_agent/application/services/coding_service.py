"""Coding service - Main orchestration for code editing."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from coding_agent.application.dto.requests import CodingRequest, ContextRequest
from coding_agent.application.dto.responses import CodingResponse
from coding_agent.application.ports.editor_port import EditorPort
from coding_agent.application.ports.file_storage_port import FileStoragePort
from coding_agent.application.ports.llm_port import LLMPort, Message
from coding_agent.application.services.context_service import ContextService
from coding_agent.config.settings import Settings
from coding_agent.domain.models import Edit, EditResult, OperationType, ValidationResult
from coding_agent.utils.errors import EditError, LLMError


class CodingService:
    """Main service for coding assistance."""

    def __init__(
        self,
        llm_client: LLMPort,
        context_service: ContextService,
        file_storage: FileStoragePort,
        edit_formats: Dict[str, EditorPort],
        settings: Settings,
    ):
        self._llm = llm_client
        self._context = context_service
        self._file_storage = file_storage
        self._edit_formats = edit_formats
        self._settings = settings

    async def process_request(self, request: CodingRequest) -> CodingResponse:
        """Process a coding request.

        Args:
            request: Coding request with message and files

        Returns:
            Response with LLM output and any applied edits
        """
        # Extract symbols mentioned in message
        mentioned_symbols = self._extract_symbols(request.message)
        request.mentioned_symbols = mentioned_symbols

        # Build context
        context_response = await self._context.build(
            ContextRequest(
                files=request.files,
                query=request.message,
                mentioned_symbols=mentioned_symbols,
            )
        )

        # Build messages for LLM
        messages = self._build_messages(
            request, context_response.context
        )

        # Call LLM
        try:
            llm_response = await self._llm.complete(messages)
        except LLMError as e:
            return CodingResponse(
                message=f"Error communicating with LLM: {e.message}",
                edit_results=[],
            )

        # Parse and apply edits if present
        edit_results: List[EditResult] = []
        if llm_response.contains_edits:
            edits = self._parse_edits(llm_response.content, request.edit_format)
            edit_results = await self._apply_edits(edits)

        return CodingResponse(
            message=llm_response.content,
            edit_results=edit_results,
            context_used=context_response.context,
            model=llm_response.model,
            usage=llm_response.usage,
        )

    def _extract_symbols(self, message: str) -> Set[str]:
        """Extract function/class names from message.

        Args:
            message: User message

        Returns:
            Set of symbol names
        """
        symbols = set()

        # Look for function calls: word()
        func_pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
        symbols.update(re.findall(func_pattern, message))

        # Look for class references: ClassName
        class_pattern = r"\b([A-Z][a-zA-Z0-9_]*)\b"
        symbols.update(re.findall(class_pattern, message))

        return symbols

    def _build_messages(
        self, request: CodingRequest, context: str
    ) -> List[Message]:
        """Build messages for LLM.

        Args:
            request: Coding request
            context: Built context

        Returns:
            List of messages
        """
        messages = []

        # System prompt based on edit format
        system_prompt = self._get_system_prompt(request.edit_format)
        messages.append(Message(role="system", content=system_prompt))

        # Context
        if context:
            messages.append(
                Message(
                    role="system",
                    content=f"Repository Context:\n{context}",
                )
            )

        # Chat history
        for msg in request.chat_history[-5:]:  # Last 5 messages
            messages.append(Message(role=msg.get("role", "user"), content=msg.get("content", "")))

        # User message
        messages.append(Message(role="user", content=request.message))

        return messages

    def _get_system_prompt(self, edit_format: str) -> str:
        """Get system prompt for edit format.

        Args:
            edit_format: Name of edit format

        Returns:
            System prompt string
        """
        if edit_format == "search_replace":
            return """You are an expert software developer. When making code changes:
1. Use SEARCH/REPLACE blocks to show exact changes
2. Include enough context in SEARCH blocks for unique matching
3. CRITICAL: Copy the EXACT formatting, whitespace, and indentation from the original file
4. Only show the parts that need to change
5. Be precise with whitespace and indentation

Format your edits like this:

filename.py
```python
<<<<<<< SEARCH
exact code to find (with exact whitespace and formatting)
=======
exact replacement code (with proper formatting)
>>>>>>> REPLACE
```
"""
        elif edit_format == "udiff":
            return """You are an expert software developer. Make code changes using unified diff format.

Rules:
- Start with file paths: --- old_file +++ new_file
- Use @@ ... @@ for hunk headers
- Mark removed lines with -
- Mark added lines with +
- Include enough context for clean application
- For new files use: --- /dev/null
"""
        else:
            return "You are an expert software developer."

    def _parse_edits(self, content: str, format_name: str) -> List[Edit]:
        """Parse edits from LLM response.

        Args:
            content: LLM response content
            format_name: Edit format name

        Returns:
            List of edits
        """
        edits = []

        if format_name in ("search_replace", "diff"):
            edits = self._parse_search_replace(content)
        elif format_name == "udiff":
            edits = self._parse_unified_diff(content)

        return edits

    def _parse_search_replace(self, content: str) -> List[Edit]:
        """Parse SEARCH/REPLACE blocks.

        Args:
            content: Response content

        Returns:
            List of edits
        """
        edits = []

        # Pattern with flexible formatting
        patterns = [
            r"(\S+\.\w+)\s*```\w*\n<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE\n```",
            r"(\S+\.\w+)\s*\n<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE",
            r"```\w*\s*\n(\S+\.\w+)\s*\n<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE\n```",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            for file_path, search, replace in matches:
                try:
                    edit = Edit(
                        file_path=Path(file_path.strip()),
                        operation=OperationType.SEARCH_REPLACE,
                        search=search,
                        replace=replace,
                    )
                    edits.append(edit)
                except ValueError:
                    continue

        return edits

    def _parse_unified_diff(self, content: str) -> List[Edit]:
        """Parse unified diff format.

        Args:
            content: Response content

        Returns:
            List of edits
        """
        edits = []

        diff_pattern = r"```diff\n(.*?)\n```"
        diff_blocks = re.findall(diff_pattern, content, re.DOTALL)

        for diff_block in diff_blocks:
            # Extract file path from diff header
            file_path = self._extract_file_from_diff(diff_block)
            if file_path:
                edit = Edit(
                    file_path=Path(file_path),
                    operation=OperationType.UNIFIED_DIFF,
                    diff_content=diff_block,
                )
                edits.append(edit)

        return edits

    def _extract_file_from_diff(self, diff_content: str) -> Optional[str]:
        """Extract file path from diff.

        Args:
            diff_content: Diff content

        Returns:
            File path or None
        """
        lines = diff_content.split("\n")
        for line in lines:
            if line.startswith("--- ") or line.startswith("+++ "):
                if "/dev/null" not in line:
                    return line.split(" ", 1)[1].strip()
        return None

    async def _apply_edits(self, edits: List[Edit]) -> List[EditResult]:
        """Apply edits to files.

        Args:
            edits: List of edits to apply

        Returns:
            List of edit results
        """
        results = []

        for edit in edits:
            try:
                # Get the appropriate editor for this format
                editor = self._edit_formats.get("search_replace")
                if edit.operation == OperationType.UNIFIED_DIFF:
                    editor = self._edit_formats.get("udiff")

                if not editor:
                    results.append(
                        EditResult.failure_result(
                            edit=edit,
                            file_path=edit.file_path,
                            error_message=f"Unknown edit format: {edit.operation}",
                        )
                    )
                    continue

                result = await editor.apply_edit(edit)
                results.append(result)

            except EditError as e:
                results.append(
                    EditResult.failure_result(
                        edit=edit,
                        file_path=edit.file_path,
                        error_message=str(e),
                    )
                )
            except Exception as e:
                results.append(
                    EditResult.failure_result(
                        edit=edit,
                        file_path=edit.file_path,
                        error_message=f"Unexpected error: {e}",
                    )
                )

        return results
