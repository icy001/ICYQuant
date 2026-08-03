"""
Log formatters.

Provides JSON and text formatters for
structuring log output in a consistent,
machine-readable format.

JSON formatter produces structured logs
suitable for ELK, Loki, and other log
aggregation systems.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from .exceptions import FormatterError
from .models import LogEntry


class JsonFormatter:
    """
    JSON log formatter.

    Formats LogEntry objects as JSON
    strings suitable for log aggregation
    systems like ELK, Loki, and Datadog.

    Output format:
        {
            "timestamp": "2026-01-01T00:00:00.000000",
            "level": "INFO",
            "logger": "icyquant",
            "message": "Order submitted",
            "trace_id": "abc-123",
            "span_id": "def-456",
            "fields": {
                "symbol": "AAPL",
                "order_id": "123456"
            }
        }

    Usage:
        formatter = JsonFormatter()
        output = formatter.format(log_entry)
    """

    def __init__(
        self,
        indent: Optional[int] = None,
        ensure_ascii: bool = False,
    ) -> None:
        """
        Initialize JSON formatter.

        Args:
            indent: JSON indentation level.
            ensure_ascii: Whether to escape non-ASCII.
        """

        self._indent = indent
        self._ensure_ascii = ensure_ascii

    def format(
        self,
        record: LogEntry,
    ) -> str:
        """
        Format a log entry as JSON string.

        Args:
            record: LogEntry to format.

        Returns:
            JSON string.

        Raises:
            FormatterError: If serialization fails.
        """

        try:
            payload = record.to_dict()
            return json.dumps(
                payload,
                default=str,
                indent=self._indent,
                ensure_ascii=self._ensure_ascii,
            )
        except (TypeError, ValueError) as exc:
            raise FormatterError(
                f"Failed to format log entry: {exc}"
            ) from exc


class TextFormatter:
    """
    Text log formatter.

    Formats LogEntry objects as
    human-readable text strings for
    console output during development.

    Output format:
        2026-01-01 00:00:00 INFO  [icyquant] Order submitted trace_id=abc-123 symbol=AAPL

    Usage:
        formatter = TextFormatter()
        output = formatter.format(log_entry)
    """

    def __init__(
        self,
        date_format: str = "%Y-%m-%d %H:%M:%S",
    ) -> None:
        """
        Initialize text formatter.

        Args:
            date_format: Date format string.
        """

        self._date_format = date_format

    def format(
        self,
        record: LogEntry,
    ) -> str:
        """
        Format a log entry as text string.

        Args:
            record: LogEntry to format.

        Returns:
            Formatted text string.
        """

        timestamp = record.timestamp.strftime(
            self._date_format
        )

        parts = [
            timestamp,
            record.level.ljust(8),
            f"[{record.logger}]",
            record.message,
        ]

        if record.trace_id:
            parts.append(f"trace_id={record.trace_id}")
        if record.span_id:
            parts.append(f"span_id={record.span_id}")

        for key, value in record.fields.items():
            parts.append(f"{key}={value}")

        return " ".join(parts)


def get_formatter(
    format_type: str = "json",
) -> Any:
    """
    Get a formatter by type.

    Args:
        format_type: Format type (json, text).

    Returns:
        Formatter instance.

    Raises:
        FormatterError: If format type is unknown.
    """

    if format_type == "json":
        return JsonFormatter()
    elif format_type in ("text", "plain"):
        return TextFormatter()
    else:
        raise FormatterError(
            f"Unknown format type: {format_type}"
        )
