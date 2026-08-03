"""
Structured logging context package.

Provides distributed context propagation,
trace correlation, sensitive data masking,
and automatic context injection for the
ICYQuant logging infrastructure.

Components:
- LogContext: Enhanced context dataclass
- ContextManager: Centralized context management
- ContextMiddleware: Request lifecycle context
- ContextPropagator: Cross-service context propagation
- DataMasker: Sensitive field masking
- ContextFilter: Automatic context enrichment
- CorrelationManager: Business correlation IDs

This package is backward-compatible with
the original context.py module-level functions.
"""

from .correlation import CorrelationManager
from .filters import ContextFilter
from .manager import (
    ContextManager,
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
)
from .masker import (
    DEFAULT_MASK_FIELDS,
    DataMasker,
    mask,
)
from .middleware import ContextMiddleware
from .models import LogContext
from .propagator import (
    HEADER_CORRELATION_ID,
    HEADER_ORDER_ID,
    HEADER_REQUEST_ID,
    HEADER_SESSION_ID,
    HEADER_SPAN_ID,
    HEADER_STRATEGY_ID,
    HEADER_TRACE_ID,
    HEADER_USER_ID,
    PROPAGATION_HEADERS,
    ContextPropagator,
)

__all__ = [
    # Models
    "LogContext",
    # Manager
    "ContextManager",
    # Middleware
    "ContextMiddleware",
    # Propagator
    "ContextPropagator",
    "PROPAGATION_HEADERS",
    "HEADER_TRACE_ID",
    "HEADER_SPAN_ID",
    "HEADER_REQUEST_ID",
    "HEADER_CORRELATION_ID",
    "HEADER_USER_ID",
    "HEADER_STRATEGY_ID",
    "HEADER_ORDER_ID",
    "HEADER_SESSION_ID",
    # Masker
    "DataMasker",
    "mask",
    "DEFAULT_MASK_FIELDS",
    # Filter
    "ContextFilter",
    # Correlation
    "CorrelationManager",
    # Backward-compat functions
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
]
