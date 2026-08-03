"""
Context manager.

Provides centralized management of the
logging context using Python's contextvars,
ensuring request-scoped context propagation
across async tasks.

Maintains backward compatibility with the
flat module-level functions from the
original context.py.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Dict, Optional

from .models import LogContext

# Primary context variable
_context: ContextVar[LogContext] = ContextVar(
    "logging_context",
    default=LogContext(),
)

# Backward-compat individual ContextVars
_trace_id: ContextVar[Optional[str]] = ContextVar(
    "trace_id", default=None
)
_span_id: ContextVar[Optional[str]] = ContextVar(
    "span_id", default=None
)
_request_id: ContextVar[Optional[str]] = ContextVar(
    "request_id", default=None
)
_user_id: ContextVar[Optional[str]] = ContextVar(
    "user_id", default=None
)
_strategy_id: ContextVar[Optional[str]] = ContextVar(
    "strategy_id", default=None
)
_order_id: ContextVar[Optional[str]] = ContextVar(
    "order_id", default=None
)


class ContextManager:
    """
    Centralized context manager.

    Provides static methods for getting,
    setting, and clearing the logging
    context. Also offers field-level
    update methods.

    Usage:
        ctx = ContextManager.get()
        ContextManager.set(LogContext(trace_id="abc"))
        ContextManager.update(trace_id="xyz")
        ContextManager.clear()
    """

    @staticmethod
    def get() -> LogContext:
        """
        Get the current logging context.

        Returns:
            Current LogContext.
        """

        return _context.get()

    @staticmethod
    def set(
        context: LogContext,
    ) -> None:
        """
        Set the logging context.

        Args:
            context: LogContext to set.
        """

        _context.set(context)
        # Sync backward-compat vars
        _trace_id.set(context.trace_id)
        _span_id.set(context.span_id)
        _request_id.set(context.request_id)
        _user_id.set(context.user_id)
        _strategy_id.set(context.strategy_id)
        _order_id.set(context.order_id)

    @staticmethod
    def update(
        **kwargs: Any,
    ) -> LogContext:
        """
        Update specific context fields.

        Creates a new context with updated
        fields, preserving existing values
        for fields not specified.

        Args:
            **kwargs: Fields to update.

        Returns:
            Updated LogContext.
        """

        current = _context.get()
        new_context = LogContext(
            trace_id=kwargs.get("trace_id", current.trace_id),
            span_id=kwargs.get("span_id", current.span_id),
            request_id=kwargs.get("request_id", current.request_id),
            correlation_id=kwargs.get("correlation_id", current.correlation_id),
            session_id=kwargs.get("session_id", current.session_id),
            user_id=kwargs.get("user_id", current.user_id),
            strategy_id=kwargs.get("strategy_id", current.strategy_id),
            order_id=kwargs.get("order_id", current.order_id),
            position_id=kwargs.get("position_id", current.position_id),
            account_id=kwargs.get("account_id", current.account_id),
            environment=kwargs.get("environment", current.environment),
            hostname=kwargs.get("hostname", current.hostname),
        )
        new_context.metadata = {
            **current.metadata,
            **kwargs.get("metadata", {}),
        }
        ContextManager.set(new_context)
        return new_context

    @staticmethod
    def clear() -> None:
        """Clear the logging context."""

        _context.set(LogContext())
        _trace_id.set(None)
        _span_id.set(None)
        _request_id.set(None)
        _user_id.set(None)
        _strategy_id.set(None)
        _order_id.set(None)

    @staticmethod
    def snapshot() -> Dict[str, Any]:
        """
        Get a dictionary snapshot of the context.

        Returns:
            Dictionary representation.
        """

        return _context.get().to_dict()


# === Backward-compatible module-level functions ===

def set_trace_id(value: Optional[str]) -> None:
    """Set the current trace ID."""

    _trace_id.set(value)
    ctx = _context.get()
    ctx.trace_id = value
    _context.set(ctx)


def get_trace_id() -> Optional[str]:
    """Get the current trace ID."""
    return _trace_id.get()


def set_span_id(value: Optional[str]) -> None:
    """Set the current span ID."""

    _span_id.set(value)
    ctx = _context.get()
    ctx.span_id = value
    _context.set(ctx)


def get_span_id() -> Optional[str]:
    """Get the current span ID."""
    return _span_id.get()


def set_request_id(value: Optional[str]) -> None:
    """Set the current request ID."""

    _request_id.set(value)
    ctx = _context.get()
    ctx.request_id = value
    _context.set(ctx)


def get_request_id() -> Optional[str]:
    """Get the current request ID."""
    return _request_id.get()


def set_user_id(value: Optional[str]) -> None:
    """Set the current user ID."""

    _user_id.set(value)
    ctx = _context.get()
    ctx.user_id = value
    _context.set(ctx)


def get_user_id() -> Optional[str]:
    """Get the current user ID."""
    return _user_id.get()


def set_strategy_id(value: Optional[str]) -> None:
    """Set the current strategy ID."""

    _strategy_id.set(value)
    ctx = _context.get()
    ctx.strategy_id = value
    _context.set(ctx)


def get_strategy_id() -> Optional[str]:
    """Get the current strategy ID."""
    return _strategy_id.get()


def set_order_id(value: Optional[str]) -> None:
    """Set the current order ID."""

    _order_id.set(value)
    ctx = _context.get()
    ctx.order_id = value
    _context.set(ctx)


def get_order_id() -> Optional[str]:
    """Get the current order ID."""
    return _order_id.get()


def set_extra(key: str, value: Any) -> None:
    """Set an extra context field (stored in metadata)."""

    ctx = _context.get()
    ctx.metadata[key] = value
    _context.set(ctx)


def get_extra(key: str, default: Any = None) -> Any:
    """Get an extra context field."""

    return _context.get().metadata.get(key, default)


def get_all_extra() -> Dict[str, Any]:
    """Get all extra context fields."""

    return dict(_context.get().metadata)


def get_context() -> LogContext:
    """Get current log context snapshot."""

    return _context.get()


def clear_context() -> None:
    """Clear all context values."""

    ContextManager.clear()
