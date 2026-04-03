"""Multi-language parser using tree-sitter with AST fallback."""

import ast
import warnings
from pathlib import Path
from typing import Dict, List, Optional

from coding_agent.application.ports.parser_port import ParserPort
from coding_agent.domain.models import Symbol, SymbolType
from coding_agent.utils.errors import ParseError

warnings.filterwarnings("ignore", category=FutureWarning)

try:
    from grep_ast import filename_to_lang
    from grep_ast.tsl import get_language, get_parser

    TREESITTER_AVAILABLE = True
except ImportError:
    TREESITTER_AVAILABLE = False


class MultiLanguageParser(ParserPort):
    """Parser supporting multiple languages via tree-sitter and AST fallback."""

    def __init__(self):
        self._cache: Dict[Path, List[Symbol]] = {}
        self._python_parser = _PythonASTParser()

    async def parse(self, file_path: Path, content: Optional[str] = None) -> List[Symbol]:
        """Parse file and extract symbols.

        Args:
            file_path: Path to file
            content: Optional pre-loaded content

        Returns:
            List of symbols
        """
        # Use tree-sitter first if available
        if TREESITTER_AVAILABLE:
            try:
                return await self._parse_with_treesitter(file_path, content)
            except Exception as e:
                # Fall through to AST for Python files
                pass

        # Fallback to Python AST
        if file_path.suffix == ".py":
            return await self._python_parser.parse(file_path, content)

        return []

    def can_parse(self, file_path: Path) -> bool:
        """Check if file can be parsed.

        Args:
            file_path: Path to file

        Returns:
            True if can parse
        """
        if file_path.suffix == ".py":
            return True
        if TREESITTER_AVAILABLE:
            lang = filename_to_lang(str(file_path))
            return lang is not None
        return False

    def get_language(self, file_path: Path) -> Optional[str]:
        """Get language identifier.

        Args:
            file_path: Path to file

        Returns:
            Language name or None
        """
        if TREESITTER_AVAILABLE:
            return filename_to_lang(str(file_path))

        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
        }
        return ext_map.get(file_path.suffix)

    async def find_references(
        self,
        symbol: Symbol,
        files: List[Path],
    ) -> Dict[Path, List[int]]:
        """Find references to symbol in files.

        Args:
            symbol: Symbol to find
            files: Files to search

        Returns:
            Dict mapping file paths to line numbers
        """
        references = {}
        # Simple text search for now
        for file_path in files:
            try:
                content = await self._read_file(file_path)
                lines = content.split("\n")
                found_lines = [
                    i + 1 for i, line in enumerate(lines) if symbol.name in line
                ]
                if found_lines:
                    references[file_path] = found_lines
            except Exception:
                continue
        return references

    async def _parse_with_treesitter(
        self, file_path: Path, content: Optional[str] = None
    ) -> List[Symbol]:
        """Parse using tree-sitter.

        Args:
            file_path: Path to file
            content: Optional content

        Returns:
            List of symbols
        """
        lang = filename_to_lang(str(file_path))
        if not lang:
            return []

        parser = get_parser(lang)
        if not parser:
            return []

        if content is None:
            content = await self._read_file(file_path)

        tree = parser.parse(bytes(content, "utf-8"))
        return self._extract_symbols_from_tree(tree.root_node, content, file_path)

    def _extract_symbols_from_tree(
        self, node, content: str, file_path: Path
    ) -> List[Symbol]:
        """Extract symbols from tree-sitter parse tree.

        Args:
            node: Root node
            content: File content
            file_path: Path to file

        Returns:
            List of symbols
        """
        symbols = []
        lines = content.split("\n")

        def traverse(node, parent: Optional[str] = None):
            node_type = node.type

            # Function definitions
            if node_type in ["function_definition", "method_definition", "function_declaration"]:
                name_node = self._find_name_node(node)
                if name_node:
                    name = name_node.text.decode("utf-8")
                    line = node.start_point[0] + 1
                    sig = self._get_node_signature(node, lines)

                    symbols.append(
                        Symbol(
                            name=name,
                            line=line,
                            symbol_type=SymbolType.FUNCTION,
                            signature=sig,
                            file_path=file_path,
                            parent=parent,
                        )
                    )
                    # Traverse children with this as parent
                    for child in node.children:
                        traverse(child, parent=name)
                    return

            # Class definitions
            elif node_type in ["class_definition", "class_declaration"]:
                name_node = self._find_name_node(node)
                if name_node:
                    name = name_node.text.decode("utf-8")
                    line = node.start_point[0] + 1
                    methods = self._extract_methods(node)

                    symbols.append(
                        Symbol(
                            name=name,
                            line=line,
                            symbol_type=SymbolType.CLASS,
                            file_path=file_path,
                            parent=parent,
                            methods=methods,
                        )
                    )
                    # Traverse children with this as parent
                    for child in node.children:
                        traverse(child, parent=name)
                    return

            # Variable definitions
            elif node_type in ["variable_declaration", "const_declaration"]:
                name_node = self._find_name_node(node)
                if name_node:
                    name = name_node.text.decode("utf-8")
                    line = node.start_point[0] + 1
                    symbols.append(
                        Symbol(
                            name=name,
                            line=line,
                            symbol_type=SymbolType.VARIABLE,
                            file_path=file_path,
                            parent=parent,
                        )
                    )

            # Recursively process children
            for child in node.children:
                traverse(child, parent)

        traverse(node)
        return symbols

    def _find_name_node(self, node) -> Optional:
        """Find the identifier/name node."""
        for child in node.children:
            if child.type in ["identifier", "name"]:
                return child
        return None

    def _get_node_signature(self, node, lines: List[str]) -> str:
        """Extract function signature from node."""
        start_line = node.start_point[0]
        end_line = min(node.end_point[0] + 1, len(lines))
        sig_lines = lines[start_line:min(start_line + 3, end_line)]
        return " ".join(line.strip() for line in sig_lines if line.strip())

    def _extract_methods(self, class_node) -> List[str]:
        """Extract method names from a class node."""
        methods = []
        for child in class_node.children:
            if child.type in ["function_definition", "method_definition"]:
                name_node = self._find_name_node(child)
                if name_node:
                    methods.append(name_node.text.decode("utf-8"))
        return methods

    async def _read_file(self, file_path: Path) -> str:
        """Read file content."""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()


class _PythonASTParser(ParserPort):
    """Python-specific AST parser."""

    async def parse(self, file_path: Path, content: Optional[str] = None) -> List[Symbol]:
        """Parse Python file using AST."""
        if content is None:
            content = await self._read_file(file_path)

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        symbols = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                args = [arg.arg for arg in node.args.args]
                signature = f"{node.name}({', '.join(args)})"

                symbols.append(
                    Symbol(
                        name=node.name,
                        line=node.lineno or 0,
                        symbol_type=SymbolType.FUNCTION,
                        signature=signature,
                        file_path=file_path,
                    )
                )

            elif isinstance(node, ast.ClassDef):
                methods = [
                    n.name for n in node.body if isinstance(n, ast.FunctionDef)
                ]
                symbols.append(
                    Symbol(
                        name=node.name,
                        line=node.lineno or 0,
                        symbol_type=SymbolType.CLASS,
                        file_path=file_path,
                        methods=methods,
                    )
                )

            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        symbols.append(
                            Symbol(
                                name=target.id,
                                line=node.lineno or 0,
                                symbol_type=SymbolType.VARIABLE,
                                file_path=file_path,
                            )
                        )

        return symbols

    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix == ".py"

    def get_language(self, file_path: Path) -> Optional[str]:
        return "python" if file_path.suffix == ".py" else None

    async def find_references(
        self, symbol: Symbol, files: List[Path]
    ) -> Dict[Path, List[int]]:
        return {}

    async def _read_file(self, file_path: Path) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
