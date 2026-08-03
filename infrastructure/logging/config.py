"""
Logging configuration.

Defines the LoggingConfig dataclass
for configuring the logging infrastructure,
including log level, format, output
destinations, and tracing integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .constants import (
    DEFAULT_CONSOLE,
    DEFAULT_FILE,
    DEFAULT_FILE_PATH,
    DEFAULT_FORMAT,
    DEFAULT_LOGGER,
    LOG_LEVELS,
)
from .exceptions import ConfigError


@dataclass
class LoggingConfig:
    """
    Logging configuration.

    Configures the behavior of the logging
    infrastructure, including log level,
    output format, and destination handlers.

    Attributes:
        level: Minimum log level (DEBUG, INFO, etc.).
        format: Output format (json, text).
        service_name: Service name for log identification.
        environment: Deployment environment.
        enable_console: Whether to output to console.
        enable_file: Whether to output to file.
        file_path: Log file path.
        enable_trace_id: Whether to include trace ID.
        enable_span_id: Whether to include span ID.
        max_file_size: Max file size in bytes before rotation.
        backup_count: Number of backup files to keep.
    """

    level: str = "INFO"
    format: str = DEFAULT_FORMAT
    service_name: str = DEFAULT_LOGGER
    environment: str = "dev"
    enable_console: bool = DEFAULT_CONSOLE
    enable_file: bool = DEFAULT_FILE
    file_path: str = DEFAULT_FILE_PATH
    enable_trace_id: bool = True
    enable_span_id: bool = True
    max_file_size: int = 100 * 1024 * 1024  # 100 MB
    backup_count: int = 5

    def __post_init__(
        self,
    ) -> None:
        """Validate configuration."""

        self.level = self.level.upper()
        if self.level not in LOG_LEVELS:
            raise ConfigError(
                f"Invalid log level: {self.level}. "
                f"Must be one of {LOG_LEVELS}"
            )

        if self.format not in ("json", "text", "plain"):
            raise ConfigError(
                f"Invalid format: {self.format}. "
                f"Must be one of json, text, plain"
            )

    @property
    def level_numeric(
        self,
    ) -> int:
        """Get numeric log level."""

        from .constants import LOG_LEVEL_NUMERIC

        return LOG_LEVEL_NUMERIC.get(self.level, 20)

    def to_dict(
        self,
    ) -> dict:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "level": self.level,
            "format": self.format,
            "service_name": self.service_name,
            "environment": self.environment,
            "enable_console": self.enable_console,
            "enable_file": self.enable_file,
            "file_path": self.file_path,
            "enable_trace_id": self.enable_trace_id,
            "enable_span_id": self.enable_span_id,
            "max_file_size": self.max_file_size,
            "backup_count": self.backup_count,
        }
