"""
ICYQuant Observability Service.
"""

from .context import (
    TraceContext,
    create_context,
    set_context,
    get_request_id,
    get_trace_id,
)

from .logger import (
    create_logger,
)

from .errors import (
    ErrorTracker,
    ErrorContext,
    create_error_context,
)

from .metrics import (
    MetricsCollector,
    Metric,
)

from .health import (
    HealthStatus,
    HealthCheck,
    healthy,
    unhealthy,
)

from .prometheus import (
    record_order,
    record_order_failure,
    record_ledger_event,
    set_active_requests,
    observe_latency,
    export_metrics,
)

from .tracing import (
    Tracer,
    SpanContext,
)

from .settings import (
    ObservabilitySettings,
    load_settings,
)

from .config import (
    ObservabilityConfig,
)

from .correlation import (
    CorrelationContext,
    create_correlation,
    set_correlation,
    get_correlation,
    update_order,
    update_event,
)


__all__ = [
    "TraceContext",
    "create_context",
    "set_context",
    "get_request_id",
    "get_trace_id",
    "create_logger",
    "ErrorTracker",
    "ErrorContext",
    "create_error_context",
    "MetricsCollector",
    "Metric",
    "HealthStatus",
    "HealthCheck",
    "healthy",
    "unhealthy",
    "record_order",
    "record_order_failure",
    "record_ledger_event",
    "set_active_requests",
    "observe_latency",
    "export_metrics",
    "Tracer",
    "SpanContext",
    "ObservabilitySettings",
    "load_settings",
    "ObservabilityConfig",
    "CorrelationContext",
    "create_correlation",
    "set_correlation",
    "get_correlation",
    "update_order",
    "update_event",
]