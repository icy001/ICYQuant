"""
Logging constants.

Defines standard log levels,
default logger names, and format
identifiers used throughout the
ICYQuant logging infrastructure.
"""

from __future__ import annotations

# Standard log levels (ordered by severity)
LOG_LEVELS = (
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
)

# Numeric level mapping (compatible with logging module)
LOG_LEVEL_NUMERIC = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

# Default logger name
DEFAULT_LOGGER = "icyquant"

# Default log format
DEFAULT_FORMAT = "json"

# Supported output formats
SUPPORTED_FORMATS = ("json", "text", "plain")

# Default log output destinations
DEFAULT_CONSOLE = True
DEFAULT_FILE = False

# Default file path
DEFAULT_FILE_PATH = "logs/icyquant.log"

# Field name constants
FIELD_TIMESTAMP = "timestamp"
FIELD_LEVEL = "level"
FIELD_LOGGER = "logger"
FIELD_MESSAGE = "message"
FIELD_TRACE_ID = "trace_id"
FIELD_SPAN_ID = "span_id"
FIELD_FIELDS = "fields"

# Trace context field names
CONTEXT_TRACE_ID = "trace_id"
CONTEXT_SPAN_ID = "span_id"
CONTEXT_REQUEST_ID = "request_id"
CONTEXT_USER_ID = "user_id"
CONTEXT_STRATEGY_ID = "strategy_id"
CONTEXT_ORDER_ID = "order_id"
