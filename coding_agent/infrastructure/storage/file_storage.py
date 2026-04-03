"""Local file storage implementation."""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from coding_agent.application.ports.file_storage_port import FileStoragePort
from coding_agent.domain.models import FileInfo
from coding_agent.utils.errors import FileError


class LocalFileStorage(FileStoragePort):
    """Local filesystem storage."""

    def __init__(self, root_path: Path = Path(".")):
        self._root = Path(root_path)
        self._backup_dir: Optional[Path] = None

    async def read(self, path: Path) -> str:
        """Read file content.

        Args:
            path: Path to file

        Returns:
            File content

        Raises:
            FileError: If file cannot be read
        """
        full_path = self._root / path
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise FileError(f"File not found: {path}", file_path=path, operation="read")
        except PermissionError:
            raise FileError(
                f"Permission denied: {path}", file_path=path, operation="read"
            )
        except Exception as e:
            raise FileError(f"Error reading file {path}: {e}", file_path=path, operation="read")

    async def write(self, path: Path, content: str) -> None:
        """Write content to file.

        Args:
            path: Path to file
            content: Content to write

        Raises:
            FileError: If file cannot be written
        """
        full_path = self._root / path
        try:
            # Ensure parent directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            raise FileError(
                f"Error writing file {path}: {e}", file_path=path, operation="write"
            )

    async def exists(self, path: Path) -> bool:
        """Check if file exists.

        Args:
            path: Path to check

        Returns:
            True if exists
        """
        full_path = self._root / path
        return full_path.exists()

    async def get_info(self, path: Path) -> FileInfo:
        """Get file information.

        Args:
            path: Path to file

        Returns:
            File info
        """
        full_path = self._root / path
        stat = full_path.stat()

        return FileInfo(
            path=path,
            language=self._detect_language(path),
            size_bytes=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime),
        )

    async def list_files(
        self,
        directory: Path,
        pattern: Optional[str] = None,
        recursive: bool = True,
    ) -> List[Path]:
        """List files in directory.

        Args:
            directory: Directory to list
            pattern: Glob pattern
            recursive: Whether to recurse

        Returns:
            List of file paths
        """
        full_dir = self._root / directory
        if not full_dir.exists():
            return []

        if pattern:
            if recursive:
                return list(full_dir.rglob(pattern))
            else:
                return list(full_dir.glob(pattern))
        else:
            if recursive:
                return [f.relative_to(self._root) for f in full_dir.rglob("*") if f.is_file()]
            else:
                return [f.relative_to(self._root) for f in full_dir.iterdir() if f.is_file()]

    async def backup(self, path: Path) -> Path:
        """Create a backup of the file.

        Args:
            path: Path to backup

        Returns:
            Path to backup
        """
        full_path = self._root / path
        if not full_path.exists():
            raise FileError(f"Cannot backup non-existent file: {path}", file_path=path)

        if self._backup_dir is None:
            self._backup_dir = Path(tempfile.mkdtemp(prefix="coding_agent_backup_"))

        backup_path = self._backup_dir / path
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.copy2(full_path, backup_path)
        except Exception as e:
            raise FileError(
                f"Failed to backup {path}: {e}", file_path=path, operation="backup"
            )

        return backup_path

    async def restore(self, backup_path: Path, original_path: Path) -> None:
        """Restore file from backup.

        Args:
            backup_path: Path to backup
            original_path: Path to restore to
        """
        full_original = self._root / original_path
        try:
            full_original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, full_original)
        except Exception as e:
            raise FileError(
                f"Failed to restore {original_path}: {e}",
                file_path=original_path,
                operation="restore",
            )

    async def get_modification_time(self, path: Path) -> datetime:
        """Get file modification time.

        Args:
            path: Path to file

        Returns:
            Modification time
        """
        full_path = self._root / path
        stat = full_path.stat()
        return datetime.fromtimestamp(stat.st_mtime)

    def _detect_language(self, path: Path) -> Optional[str]:
        """Detect language from file extension.

        Args:
            path: File path

        Returns:
            Language identifier or None
        """
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".html": "html",
            ".css": "css",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".rs": "rust",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".md": "markdown",
            ".txt": "text",
        }
        return ext_map.get(path.suffix)
