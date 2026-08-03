"""
Log record builder.

Provides functions for constructing
LogEntry objects from parameters,
automatically injecting context from
the context management layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from .context import get_context
from .models import LogEntry


def build_record(
    level: str,
    logger: str,
    message: str,
    **fields: Any,
) -> LogEntry:
    """
    Build a log record with automatic context injection.

    Automatically injects trace_id, span_id,
    request_id, and other context fields from
    the current context, merging them with
    any explicitly provided fields.

    Args:
        level: Log level (DEBUG, INFO, etc.).
        logger: Logger name.
        message: Log message.
        **fields: Additional structured fields.

    Returns:
        LogEntry with context injected.
    """

    # Extract trace_id and span_id from explicit fields
    trace_id = fields.pop("trace_id", None)
    span_id = fields.pop("span_id", None)

    # Inject from context if not explicitly provided
    ctx = get_context()

    if trace_id is None:
        trace_id = ctx.trace_id
    if span_id is None:
        span_id = ctx.span_id

    # Merge context fields
    context_fields = {}
    if ctx.request_id is not None:
        context_fields["request_id"] = ctx.request_id
    if ctx.user_id is not None:
        context_fields["user_id"] = ctx.user_id
    if ctx.strategy_id is not None:
        context_fields["strategy_id"] = ctx.strategy_id
    if ctx.order_id is not None:
        context_fields["order_id"] = ctx.order_id

    # Context fields are overridden by explicit fields
    merged = {**ctx.extra, **context_fields, **fields}

    return LogEntry(
        timestamp=datetime.utcnow(),
        level=level.upper(),
        logger=logger,
        message=message,
        trace_id=trace_id,
        span_id=span_id,
        fields=merged,
    )


def build_record_from_context(
    level: str,
    logger: str,
    message: str,
    fields: Optional[Dict[str, Any]] = None,
) -> LogEntry:
    """
    Build a log record from explicit fields dict.

    Similar to build_record but accepts a fields
    dictionary instead of keyword arguments.

    Args:
        level: Log level.
        logger: Logger name.
        message: Log message.
        fields: Optional fields dictionary.

    Returns:
        LogEntry with context injected.
    """

    return build_record(
        level=level,
        logger=logger,
        message=message,
        **(fields or {}),
    )
