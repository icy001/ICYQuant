"""
Log entry models.

Defines the core data structures for
log records, including LogEntry.

LogContext has been moved to the
context/ subpackage for enhanced
distributed tracing support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

# Re-export LogContext from context subpackage for backward compat
from .context.models import LogContext


@dataclass
class LogEntry:
    """
    A single structured log entry.

    Represents a complete log record with
    timestamp, level, logger name, message,
    tracing context, and additional fields.

    Attributes:
        timestamp: When the log was created.
        level: Log level (DEBUG, INFO, etc.).
        logger: Logger name that produced the entry.
        message: Human-readable log message.
        trace_id: Optional distributed trace ID.
        span_id: Optional span ID within the trace.
        fields: Additional structured fields.
    """

    timestamp: datetime
    level: str
    logger: str
    message: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation of the log entry.
        """

        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "logger": self.logger,
            "message": self.message,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "fields": self.fields,
        }

    def to_json(
        self,
    ) -> str:
        """
        Convert to JSON string.

        Returns:
            JSON string representation.
        """

        import json

        return json.dumps(self.to_dict(), default=str)
