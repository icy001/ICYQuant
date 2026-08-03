"""
Structured logging infrastructure.

Provides production-grade structured logging
for the ICYQuant platform with JSON output,
context management, distributed tracing
support, and multi-handler dispatch.

Features:
- JSON and text log formatters
- Context-local trace ID and span ID
- Automatic context injection into log records
- Named logger registry
- Level-based filtering
- Multi-handler dispatch (sync + async)
- Handler framework (Console, File, Rotating, Kafka, ES)
- Logger manager for centralized configuration
- Log filter pipeline (Level, Sampling, Composite)
- Health monitoring

Usage:
    from infrastructure.logging import (
        Logger, LoggingConfig,
        ConsoleHandler, FileHandler,
        LoggerManager,
    )

    manager = LoggerManager(config=LoggingConfig(level="DEBUG"))
    manager.add_handler(ConsoleHandler())

    logger = manager.get_logger("strategy")
    logger.info("Order submitted", symbol="AAPL", order_id="123")

    # Async logging with handlers
    await logger.ainfo("Async log", order_id="456")
"""

from .config import LoggingConfig
from .constants import (
    DEFAULT_FORMAT,
    DEFAULT_LOGGER,
    LOG_LEVELS,
    LOG_LEVEL_NUMERIC,
)
from .context import (
    clear_context,
    get_all_extra,
    get_context,
    get_extra,
    get_order_id,
    get_request_id,
    get_span_id,
    get_strategy_id,
    get_trace_id,
    get_user_id,
    set_extra,
    set_order_id,
    set_request_id,
    set_span_id,
    set_strategy_id,
    set_trace_id,
    set_user_id,
    # New context components (Part 1.4)
    ContextManager,
    ContextMiddleware,
    ContextPropagator,
    ContextFilter,
    CorrelationManager,
    DataMasker,
    mask,
    DEFAULT_MASK_FIELDS,
    PROPAGATION_HEADERS,
    HEADER_TRACE_ID,
    HEADER_SPAN_ID,
    HEADER_REQUEST_ID,
    HEADER_CORRELATION_ID,
    HEADER_USER_ID,
    HEADER_STRATEGY_ID,
    HEADER_ORDER_ID,
    HEADER_SESSION_ID,
)
from .exceptions import (
    ConfigError,
    ContextError,
    FormatterError,
    HandlerError,
    LoggingError,
)
from .filters import (
    CompositeFilter,
    FieldFilter,
    LevelFilter,
    LogFilter,
    LoggerNameFilter,
    SamplingFilter,
)
from .formatter import (
    JsonFormatter,
    TextFormatter,
    get_formatter,
)
from .handlers import (
    ConsoleHandler,
    ElasticsearchHandler,
    FileHandler,
    KafkaLogHandler,
    LogHandler,
    NullHandler,
    RotatingFileHandler,
)
from .health import LoggingHealth
from .logger import (
    Logger,
    clear_loggers,
    get_logger,
)
from .manager import LoggerManager
from .models import LogContext, LogEntry
from .record import build_record, build_record_from_context
from .queue import LogQueue
from .batch import BatchCollector
from .worker import LoggingWorker
from .dispatcher import LogDispatcher
from .buffer import MemoryBuffer
from .policy import BackpressurePolicy
from .metrics import LoggingMetrics
from .pipeline import LoggingPipeline
# Part 1.5: Bootstrap & Integration
from .service import LoggingService
from .scheduler import LoggingScheduler
from .lifecycle import LoggingLifecycle
from .container import LoggingContainer, register_logging
from .registry import LoggingRegistry
from .diagnostics import LoggingDiagnostics
from .telemetry import LoggingTelemetry
from .bootstrap import LoggingBootstrap

__all__ = [
    # Logger
    "Logger",
    "get_logger",
    "clear_loggers",
    # Logger Manager
    "LoggerManager",
    # Config
    "LoggingConfig",
    # Models
    "LogEntry",
    "LogContext",
    # Record Builder
    "build_record",
    "build_record_from_context",
    # Formatters
    "JsonFormatter",
    "TextFormatter",
    "get_formatter",
    # Handlers
    "LogHandler",
    "ConsoleHandler",
    "FileHandler",
    "RotatingFileHandler",
    "KafkaLogHandler",
    "ElasticsearchHandler",
    "NullHandler",
    # Filters
    "LogFilter",
    "LevelFilter",
    "SamplingFilter",
    "LoggerNameFilter",
    "CompositeFilter",
    "FieldFilter",
    # Context
    "set_trace_id",
    "get_trace_id",
    "set_span_id",
    "get_span_id",
    "set_request_id",
    "get_request_id",
    "set_user_id",
    "get_user_id",
    "set_strategy_id",
    "get_strategy_id",
    "set_order_id",
    "get_order_id",
    "set_extra",
    "get_extra",
    "get_all_extra",
    "get_context",
    "clear_context",
    # Health
    "LoggingHealth",
    # Constants
    "LOG_LEVELS",
    "LOG_LEVEL_NUMERIC",
    "DEFAULT_LOGGER",
    "DEFAULT_FORMAT",
    # Exceptions
    "LoggingError",
    "FormatterError",
    "HandlerError",
    "ConfigError",
    "ContextError",
    # Async Pipeline (Part 1.3)
    "LogQueue",
    "BatchCollector",
    "LoggingWorker",
    "LogDispatcher",
    "MemoryBuffer",
    "BackpressurePolicy",
    "LoggingMetrics",
    "LoggingPipeline",
    # Context Propagation (Part 1.4)
    "ContextManager",
    "ContextMiddleware",
    "ContextPropagator",
    "ContextFilter",
    "CorrelationManager",
    "DataMasker",
    "mask",
    "DEFAULT_MASK_FIELDS",
    "PROPAGATION_HEADERS",
    "HEADER_TRACE_ID",
    "HEADER_SPAN_ID",
    "HEADER_REQUEST_ID",
    "HEADER_CORRELATION_ID",
    "HEADER_USER_ID",
    "HEADER_STRATEGY_ID",
    "HEADER_ORDER_ID",
    "HEADER_SESSION_ID",
    # Bootstrap & Integration (Part 1.5)
    "LoggingService",
    "LoggingScheduler",
    "LoggingLifecycle",
    "LoggingContainer",
    "register_logging",
    "LoggingRegistry",
    "LoggingDiagnostics",
    "LoggingTelemetry",
    "LoggingBootstrap",
]
