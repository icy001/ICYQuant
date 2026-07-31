"""
ICYQuant Core Logging Module.

Production-grade structured logging layer.

Responsibilities:

- Unified application logging
- Structured event logging
- Request correlation
- Trading event traceability
- Audit logging foundation

Python:
    3.12+

Logging Stack:
    structlog
    standard logging
"""

from __future__ import annotations

import logging
import sys

from collections.abc import Awaitable, Callable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from enum import Enum
from threading import RLock
from time import perf_counter
from typing import Any, Final, Iterator, Optional
from uuid import uuid4

try:
    from starlette.requests import Request
    from starlette.responses import Response
except ImportError:
    Request = None  # type: ignore
    Response = None  # type: ignore

try:
    import structlog
    from structlog.types import EventDict
    from structlog.typing import Processor
except ImportError:
    structlog = None  # type: ignore
    EventDict = None  # type: ignore
    Processor = None  # type: ignore


# ============================================================================
# Constants
# ============================================================================


LOGGER_NAME: Final[str] = "icyquant"

DEFAULT_LOG_FORMAT: Final[str] = (
    "%(asctime)s "
    "%(levelname)s "
    "%(name)s "
    "%(message)s"
)


# ============================================================================
# Logger Types
# ============================================================================


class LoggerType(str, Enum):
    """
    ICYQuant logger categories.

    Different domains have independent
    logging streams.
    """

    APPLICATION = "application"

    API = "api"

    DATABASE = "database"

    EVENT = "event"

    TRADING = "trading"

    AUDIT = "audit"

    SECURITY = "security"

    PERFORMANCE = "performance"


# ============================================================================
# Log Event Level
# ============================================================================


class EventLevel(str, Enum):
    """
    Business event severity.
    """

    DEBUG = "debug"

    INFO = "info"

    WARNING = "warning"

    ERROR = "error"

    CRITICAL = "critical"


# ============================================================================
# Logging Context
# ============================================================================


@dataclass(
    frozen=True,
)
class LogContext:
    """
    Runtime logging context.

    Used to trace:

        API Request
        Trading Order
        Event Processing
        Risk Decision
    """

    request_id: Optional[str] = None

    trace_id: Optional[str] = None

    user_id: Optional[str] = None

    account_id: Optional[str] = None

    strategy_id: Optional[str] = None

    order_id: Optional[str] = None


# ============================================================================
# Context Storage
# ============================================================================


_log_context: ContextVar[
    LogContext
] = ContextVar(
    "icyquant_log_context",
    default=LogContext(),
)


def get_log_context() -> LogContext:
    """
    Get current logging context.

    Returns:
        Current LogContext.
    """

    return _log_context.get()


def set_log_context(
    context: LogContext,
) -> None:
    """
    Set current logging context.

    Args:
        context:
            Runtime log context.
    """

    _log_context.set(
        context
    )


def clear_log_context() -> None:
    """
    Clear current logging context.
    """

    _log_context.set(
        LogContext()
    )


# ============================================================================
# Logger Name Resolver
# ============================================================================


def get_logger_name(
    logger_type: LoggerType,
) -> str:
    """
    Build logger name.

    Example:

        icyquant.trading
        icyquant.audit
    """

    return (
        f"{LOGGER_NAME}."
        f"{logger_type.value}"
    )


# ============================================================================
# Base Logger Creation
# ============================================================================


def create_standard_logger(
    name: str,
) -> logging.Logger:
    """
    Create standard Python logger.

    This is the foundation layer.

    Structlog integration will be
    added in next parts.
    """

    logger = logging.getLogger(
        name
    )

    if not logger.handlers:

        handler = logging.StreamHandler(
            sys.stdout
        )

        formatter = logging.Formatter(
            DEFAULT_LOG_FORMAT
        )

        handler.setFormatter(
            formatter
        )

        logger.addHandler(
            handler
        )

        logger.setLevel(
            logging.INFO
        )

    return logger


# ============================================================================
# Structlog Integration
# ============================================================================


def add_application_context(
    logger: Any,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Inject runtime application context.
    """

    context = get_log_context()

    event_dict["request_id"] = context.request_id
    event_dict["trace_id"] = context.trace_id
    event_dict["user_id"] = context.user_id
    event_dict["account_id"] = context.account_id
    event_dict["strategy_id"] = context.strategy_id
    event_dict["order_id"] = context.order_id

    return event_dict


def remove_none_fields(
    logger: Any,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Remove empty fields.

    Keep log output compact.
    """

    return {
        key: value
        for key, value in event_dict.items()
        if value is not None
    }


def build_processors() -> list[Processor]:
    """
    Build structlog processor pipeline.
    """

    return [

        structlog.contextvars.merge_contextvars,

        structlog.processors.add_log_level,

        structlog.processors.TimeStamper(
            fmt="iso",
            utc=True,
        ),

        add_application_context,

        remove_none_fields,

        structlog.processors.StackInfoRenderer(),

        structlog.processors.format_exc_info,

    ]


# ============================================================================
# Renderer
# ============================================================================


def build_json_renderer() -> Processor:
    """
    Production JSON renderer.
    """

    return structlog.processors.JSONRenderer()


def build_console_renderer() -> Processor:
    """
    Local development renderer.
    """

    return structlog.dev.ConsoleRenderer(
        colors=True,
    )


# ============================================================================
# Logging Configuration
# ============================================================================


def configure_logging(
    *,
    json_logs: bool = True,
    level: int = logging.INFO,
) -> None:
    """
    Configure application logging.

    Args:

        json_logs:
            Enable JSON rendering.

        level:
            Python logging level.
    """

    logging.basicConfig(
        format="%(message)s",
        level=level,
        stream=sys.stdout,
        force=True,
    )

    renderer: Processor

    if json_logs:
        renderer = build_json_renderer()
    else:
        renderer = build_console_renderer()

    structlog.configure(

        processors=[
            *build_processors(),
            renderer,
        ],

        wrapper_class=structlog.make_filtering_bound_logger(
            level,
        ),

        logger_factory=structlog.stdlib.LoggerFactory(),

        cache_logger_on_first_use=True,
    )


# ============================================================================
# Logger Factory
# ============================================================================


def get_logger(
    logger_type: LoggerType = LoggerType.APPLICATION,
):
    """
    Return configured structlog logger.
    """

    return structlog.get_logger(
        get_logger_name(
            logger_type
        )
    )


# ============================================================================
# Domain Logger
# ============================================================================

from collections.abc import Mapping


class DomainLogger:
    """
    Base logger wrapper.

    Provides strongly-typed logging methods
    for business domains.
    """

    def __init__(
        self,
        logger_type: LoggerType,
    ) -> None:

        self._logger = get_logger(
            logger_type
        )

    def debug(
        self,
        event: str,
        **kwargs: Any,
    ) -> None:

        self._logger.debug(
            event,
            **kwargs,
        )

    def info(
        self,
        event: str,
        **kwargs: Any,
    ) -> None:

        self._logger.info(
            event,
            **kwargs,
        )

    def warning(
        self,
        event: str,
        **kwargs: Any,
    ) -> None:

        self._logger.warning(
            event,
            **kwargs,
        )

    def error(
        self,
        event: str,
        **kwargs: Any,
    ) -> None:

        self._logger.error(
            event,
            **kwargs,
        )

    def exception(
        self,
        event: str,
        **kwargs: Any,
    ) -> None:

        self._logger.exception(
            event,
            **kwargs,
        )


# ============================================================================
# Trading Logger
# ============================================================================


class TradingLogger(
    DomainLogger,
):
    """
    Trading execution logger.
    """

    def __init__(self) -> None:

        super().__init__(
            LoggerType.TRADING
        )

    def order_created(
        self,
        *,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> None:

        self.info(

            "order_created",

            order_id=order_id,

            symbol=symbol,

            side=side,

            quantity=quantity,

            price=price,

        )

    def order_filled(
        self,
        *,
        order_id: str,
        filled_qty: float,
        avg_price: float,
    ) -> None:

        self.info(

            "order_filled",

            order_id=order_id,

            filled_qty=filled_qty,

            average_price=avg_price,

        )

    def order_cancelled(
        self,
        *,
        order_id: str,
        reason: str,
    ) -> None:

        self.warning(

            "order_cancelled",

            order_id=order_id,

            reason=reason,

        )


# ============================================================================
# Audit Logger
# ============================================================================


class AuditLogger(
    DomainLogger,
):
    """
    Compliance audit logger.
    """

    def __init__(self) -> None:

        super().__init__(
            LoggerType.AUDIT
        )

    def audit(
        self,
        action: str,
        *,
        operator: str,
        resource: str,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> None:

        self.info(

            "audit",

            action=action,

            operator=operator,

            resource=resource,

            metadata=dict(metadata or {}),

        )


# ============================================================================
# Security Logger
# ============================================================================


class SecurityLogger(
    DomainLogger,
):
    """
    Security event logger.
    """

    def __init__(self) -> None:

        super().__init__(
            LoggerType.SECURITY
        )

    def login_success(
        self,
        user_id: str,
    ) -> None:

        self.info(

            "login_success",

            user_id=user_id,

        )

    def login_failed(
        self,
        *,
        username: str,
        ip: str,
    ) -> None:

        self.warning(

            "login_failed",

            username=username,

            ip=ip,

        )

    def permission_denied(
        self,
        *,
        user_id: str,
        resource: str,
    ) -> None:

        self.error(

            "permission_denied",

            user_id=user_id,

            resource=resource,

        )


# ============================================================================
# Event Logger
# ============================================================================


class EventLogger(
    DomainLogger,
):
    """
    Event Bus logger.
    """

    def __init__(self) -> None:

        super().__init__(
            LoggerType.EVENT
        )

    def published(
        self,
        *,
        topic: str,
        event_type: str,
    ) -> None:

        self.info(

            "event_published",

            topic=topic,

            event_type=event_type,

        )

    def consumed(
        self,
        *,
        topic: str,
        event_type: str,
        latency_ms: float,
    ) -> None:

        self.info(

            "event_consumed",

            topic=topic,

            event_type=event_type,

            latency_ms=latency_ms,

        )


# ============================================================================
# Performance Logger
# ============================================================================


class PerformanceLogger(
    DomainLogger,
):
    """
    Performance profiling logger.
    """

    def __init__(self) -> None:

        super().__init__(
            LoggerType.PERFORMANCE
        )

    def duration(
        self,
        *,
        operation: str,
        elapsed_ms: float,
    ) -> None:

        self.info(

            "performance",

            operation=operation,

            elapsed_ms=elapsed_ms,

        )


class Timer:
    """
    Lightweight performance timer.

    Example:

        with Timer(logger, "factor_calc"):
            ...
    """

    def __init__(
        self,
        logger: PerformanceLogger,
        operation: str,
    ) -> None:

        self.logger = logger
        self.operation = operation

    def __enter__(self):

        self._start = perf_counter()

        return self

    def __exit__(
        self,
        exc_type,
        exc,
        tb,
    ) -> None:

        elapsed = (
            perf_counter() - self._start
        ) * 1000

        self.logger.duration(

            operation=self.operation,

            elapsed_ms=elapsed,

        )


# ============================================================================
# Correlation ID Utilities
# ============================================================================


def generate_trace_id() -> str:
    """
    Generate distributed trace id.
    """

    return uuid4().hex


def generate_request_id() -> str:
    """
    Generate request identifier.
    """

    return uuid4().hex


@contextmanager
def logging_context(
    *,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    user_id: Optional[str] = None,
    account_id: Optional[str] = None,
    strategy_id: Optional[str] = None,
    order_id: Optional[str] = None,
) -> Iterator[LogContext]:
    """
    Temporarily replace logging context.

    Fields not explicitly set are inherited from the current context.
    request_id and trace_id are auto-generated if not provided and
    not already present in the current context.

    Uses ContextVar token for safe nested resets.
    """

    previous = get_log_context()

    context = LogContext(
        request_id=request_id or previous.request_id or generate_request_id(),
        trace_id=trace_id or previous.trace_id or generate_trace_id(),
        user_id=user_id if user_id is not None else previous.user_id,
        account_id=account_id if account_id is not None else previous.account_id,
        strategy_id=strategy_id if strategy_id is not None else previous.strategy_id,
        order_id=order_id if order_id is not None else previous.order_id,
    )

    token: Token = _log_context.set(context)

    try:
        yield context
    finally:
        _log_context.reset(token)


# ============================================================================
# Logger Binding
# ============================================================================


def bind_context(
    **kwargs: Any,
) -> None:
    """
    Merge fields into current logging context.
    """

    current = get_log_context()

    updated = LogContext(
        request_id=kwargs.get(
            "request_id",
            current.request_id,
        ),
        trace_id=kwargs.get(
            "trace_id",
            current.trace_id,
        ),
        user_id=kwargs.get(
            "user_id",
            current.user_id,
        ),
        account_id=kwargs.get(
            "account_id",
            current.account_id,
        ),
        strategy_id=kwargs.get(
            "strategy_id",
            current.strategy_id,
        ),
        order_id=kwargs.get(
            "order_id",
            current.order_id,
        ),
    )

    set_log_context(updated)


# ============================================================================
# Exception Logging
# ============================================================================


def log_exception(
    logger: DomainLogger,
    exc: Exception,
    *,
    operation: str,
    **kwargs: Any,
) -> None:
    """
    Log exception with context.
    """

    logger.exception(
        "exception",

        operation=operation,

        exception_type=type(exc).__name__,

        exception=str(exc),

        **kwargs,
    )


# ============================================================================
# FastAPI Middleware Support
# ============================================================================

try:
    from starlette.requests import Request
    from starlette.responses import Response

    RequestHandler = Callable[
        [Request],
        Awaitable[Response],
    ]


    async def logging_middleware(
        request: Request,
        call_next: RequestHandler,
    ) -> Response:
        """
        Request logging middleware.

        Ensures request_finished is logged even on exceptions.
        """

        request_id = (
            request.headers.get(
                "X-Request-ID"
            )
            or generate_request_id()
        )

        trace_id = (
            request.headers.get(
                "X-Trace-ID"
            )
            or generate_trace_id()
        )

        with logging_context(
            request_id=request_id,
            trace_id=trace_id,
        ):

            logger = TradingLogger()

            logger.info(

                "request_started",

                method=request.method,

                path=request.url.path,
            )

            try:
                response = await call_next(
                    request
                )
            except Exception:
                logger.error(

                    "request_failed",

                    method=request.method,

                    path=request.url.path,
                )
                raise

            response.headers[
                "X-Request-ID"
            ] = request_id

            response.headers[
                "X-Trace-ID"
            ] = trace_id

            logger.info(

                "request_finished",

                status_code=response.status_code,
            )

            return response


except ImportError:
    # starlette / fastapi not installed — skip middleware
    RequestHandler = None  # type: ignore
    Request = None  # type: ignore
    Response = None  # type: ignore


# ============================================================================
# Logger Registry
# ============================================================================

_logger_registry: dict[str, Any] = {}

_registry_lock = RLock()


def get_or_create_logger(
    logger_type: LoggerType,
):
    """
    Return cached logger instance.
    """

    name = get_logger_name(
        logger_type
    )

    with _registry_lock:

        logger = _logger_registry.get(
            name
        )

        if logger is not None:
            return logger

        logger = get_logger(
            logger_type
        )

        _logger_registry[name] = logger

        return logger


def clear_logger_registry() -> None:
    """
    Clear logger cache.
    """

    with _registry_lock:
        _logger_registry.clear()


# ============================================================================
# Bootstrap
# ============================================================================

_logging_initialized = False


def initialize_logging(
    *,
    json_logs: bool = True,
    level: int = logging.INFO,
) -> None:
    """
    Initialize logging once.
    """

    global _logging_initialized

    if _logging_initialized:
        return

    configure_logging(
        json_logs=json_logs,
        level=level,
    )

    _logging_initialized = True


# ============================================================================
# Shutdown
# ============================================================================


def shutdown_logging() -> None:
    """
    Flush logging subsystem.
    """

    logging.shutdown()

    clear_logger_registry()


# ============================================================================
# Health Check
# ============================================================================


def logging_health() -> dict[str, Any]:
    """
    Logging subsystem status.
    """

    return {

        "initialized": _logging_initialized,

        "registered_loggers": len(
            _logger_registry
        ),

        "context_active": (
            get_log_context().trace_id
            is not None
        ),
    }


# ============================================================================
# Public API
# ============================================================================

__all__ = [

    "configure_logging",

    "initialize_logging",

    "shutdown_logging",

    "logging_health",

    "get_logger",

    "get_or_create_logger",

    "LoggerType",

    "TradingLogger",

    "AuditLogger",

    "SecurityLogger",

    "EventLogger",

    "PerformanceLogger",

    "logging_context",

    "bind_context",

    "generate_trace_id",

    "generate_request_id",

    "set_log_context",

    "get_log_context",

    "clear_log_context",

]


# ============================================================================
# Backward-compatible API
# ============================================================================


def setup_logging(
    level: Optional[str] = None,
) -> None:
    """
    Initialize root logging configuration.

    Preserved for backward compatibility with existing callers
    in core/bootstrap.py and other modules.
    """

    from core.settings import get_settings

    settings = get_settings()
    log_level = level or settings.LOG_LEVEL
    numeric_level = getattr(
        logging, log_level.upper(), logging.INFO
    )

    handlers = [
        logging.StreamHandler(sys.stdout),
    ]

    if settings.LOG_FILE:
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            settings.LOG_FILE,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )

    logging.getLogger("uvicorn").setLevel(numeric_level)
    logging.getLogger("uvicorn.access").setLevel(
        logging.WARNING
    )
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.WARNING
    )


def get_standard_logger(name: str) -> logging.Logger:
    """
    Get or create a standard Python logger by name.

    Preserved for backward compatibility.
    """

    return logging.getLogger(name)