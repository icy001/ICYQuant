"""
Rotating file log handler.

Extends FileHandler with log rotation
based on file size or time interval.
Supports configurable backup count
and retention policy.

Rotation strategies:
- Size: Rotate when file exceeds max_size bytes
- Daily: Rotate at midnight each day
- Weekly: Rotate once per week
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from ..models import LogEntry
from .file import FileHandler


class RotatingFileHandler(FileHandler):
    """
    Rotating file log handler.

    Rotates log files when they exceed
    a specified size or time interval,
    keeping a configurable number of
    backup files.

    Features:
    - Size-based rotation (e.g. 100 MB)
    - Time-based rotation (daily, weekly)
    - Configurable backup count
    - Automatic suffix numbering (.1, .2, ...)

    Usage:
        handler = RotatingFileHandler(
            file_path="logs/app.log",
            max_size=100 * 1024 * 1024,  # 100 MB
            backup_count=5,
        )
        await handler.startup()
        await handler.emit(log_entry)
        await handler.shutdown()
    """

    def __init__(
        self,
        file_path: Union[str, Path],
        max_size: int = 100 * 1024 * 1024,
        backup_count: int = 5,
        rotation_mode: str = "size",
        format_type: str = "json",
        encoding: str = "utf-8",
        name: Optional[str] = None,
    ) -> None:
        """
        Initialize rotating file handler.

        Args:
            file_path: Path to the log file.
            max_size: Max file size in bytes (for size mode).
            backup_count: Number of backup files to keep.
            rotation_mode: Rotation mode (size, daily, weekly).
            format_type: Output format (json, text).
            encoding: File encoding.
            name: Optional handler name.
        """

        super().__init__(
            file_path=file_path,
            format_type=format_type,
            encoding=encoding,
            name=name,
        )
        self._max_size = max_size
        self._backup_count = backup_count
        self._rotation_mode = rotation_mode
        self._last_rotation: Optional[datetime] = None
        self._current_date: Optional[str] = None

    async def emit(
        self,
        record: LogEntry,
    ) -> None:
        """
        Write a log record with rotation check.

        Args:
            record: LogEntry to write.
        """

        # Check if rotation is needed
        if self._should_rotate():
            await self._rotate()

        # Write via parent
        await super().emit(record)

    def _should_rotate(
        self,
    ) -> bool:
        """Check if rotation is needed."""

        if not self._file_path.exists():
            return False

        if self._rotation_mode == "size":
            return (
                self._file_path.stat().st_size
                >= self._max_size
            )
        elif self._rotation_mode == "daily":
            today = datetime.now().strftime("%Y-%m-%d")
            if self._current_date is None:
                self._current_date = today
                return False
            return today != self._current_date
        elif self._rotation_mode == "weekly":
            now = datetime.now()
            if self._last_rotation is None:
                self._last_rotation = now
                return False
            days_since = (now - self._last_rotation).days
            return days_since >= 7

        return False

    async def _rotate(
        self,
    ) -> None:
        """Perform file rotation."""

        # Close current file
        if self._file is not None:
            self._file.close()
            self._file = None

        # Rotate backup files: .4 -> .5, .3 -> .4, etc.
        for i in range(
            self._backup_count, 0, -1
        ):
            src = self._file_path.with_suffix(
                f"{self._file_path.suffix}.{i}"
            )
            dst = self._file_path.with_suffix(
                f"{self._file_path.suffix}.{i + 1}"
            )
            if src.exists():
                if dst.exists():
                    dst.unlink()
                src.rename(dst)

        # Move current file to .1
        backup = self._file_path.with_suffix(
            f"{self._file_path.suffix}.1"
        )
        if backup.exists():
            backup.unlink()
        if self._file_path.exists():
            self._file_path.rename(backup)

        # Remove old backups beyond backup_count
        for i in range(
            self._backup_count + 1,
            self._backup_count + 10,
        ):
            old = self._file_path.with_suffix(
                f"{self._file_path.suffix}.{i}"
            )
            if old.exists():
                old.unlink()

        # Update rotation tracking
        self._last_rotation = datetime.now()
        self._current_date = datetime.now().strftime(
            "%Y-%m-%d"
        )

        # Reopen file
        self._file = open(
            self._file_path,
            "a",
            encoding=self._encoding,
        )

    def get_status(
        self,
    ) -> dict:
        """Get handler status."""

        status = super().get_status()
        status["max_size"] = self._max_size
        status["backup_count"] = self._backup_count
        status["rotation_mode"] = self._rotation_mode
        status["file_size"] = (
            self._file_path.stat().st_size
            if self._file_path.exists()
            else 0
        )
        return status
