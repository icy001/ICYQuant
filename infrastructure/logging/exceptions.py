"""
Logging exceptions.

Defines the exception hierarchy for
the logging infrastructure, enabling
consistent error handling across all
logging components.
"""

from __future__ import annotations


class LoggingError(Exception):
    """
    Base logging exception.

    All logging-related errors inherit
    from this base class.
    """


class FormatterError(LoggingError):
    """
    Formatter error.

    Raised when log formatting fails,
    such as serialization errors in
    the JSON formatter.
    """


class HandlerError(LoggingError):
    """
    Handler error.

    Raised when a log handler fails
    to write or dispatch a log record.
    """


class ConfigError(LoggingError):
    """
    Configuration error.

    Raised when logging configuration
    contains invalid values.
    """


class ContextError(LoggingError):
    """
    Context error.

    Raised when log context operations
    fail, such as invalid trace ID
    manipulation.
    """
