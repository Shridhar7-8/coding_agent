"""Abstract file storage interface."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from coding_agent.domain.models import FileInfo


class FileStoragePort(ABC):
    """Abstract interface for file storage operations."""

    @abstractmethod
    async def read(self, path: Path) -> str:
        """Read file content.

        Args:
            path: Path to file

        Returns:
            File content as string

        Raises:
            FileError: If file cannot be read
        """
        raise NotImplementedError

    @abstractmethod
    async def write(self, path: Path, content: str) -> None:
        """Write content to file.

        Args:
            path: Path to file
            content: Content to write

        Raises:
            FileError: If file cannot be written
        """
        raise NotImplementedError

    @abstractmethod
    async def exists(self, path: Path) -> bool:
        """Check if file exists.

        Args:
            path: Path to check

        Returns:
            True if exists, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    async def get_info(self, path: Path) -> FileInfo:
        """Get file information.

        Args:
            path: Path to file

        Returns:
            File information
        """
        raise NotImplementedError

    @abstractmethod
    async def list_files(
        self,
        directory: Path,
        pattern: Optional[str] = None,
        recursive: bool = True,
    ) -> List[Path]:
        """List files in directory.

        Args:
            directory: Directory to list
            pattern: Glob pattern to filter
            recursive: Whether to recurse into subdirectories

        Returns:
            List of file paths
        """
        raise NotImplementedError

    @abstractmethod
    async def backup(self, path: Path) -> Path:
        """Create a backup of the file.

        Args:
            path: Path to backup

        Returns:
            Path to backup file
        """
        raise NotImplementedError

    @abstractmethod
    async def restore(self, backup_path: Path, original_path: Path) -> None:
        """Restore file from backup.

        Args:
            backup_path: Path to backup
            original_path: Path to restore to
        """
        raise NotImplementedError

    @abstractmethod
    async def get_modification_time(self, path: Path) -> datetime:
        """Get file modification time.

        Args:
            path: Path to file

        Returns:
            Modification time
        """
        raise NotImplementedError
