"""
Tracing constants.
"""

from __future__ import annotations

# Trace context headers
TRACE_HEADER = "X-Trace-ID"
SPAN_HEADER = "X-Span-ID"
PARENT_SPAN_HEADER = "X-Parent-Span-ID"
SAMPLED_HEADER = "X-Sampled"

# W3C Trace Context headers
W3C_TRACEPARENT = "traceparent"
W3C_TRACESTATE = "tracestate"

# Span kinds
SPAN_KIND_INTERNAL = "internal"
SPAN_KIND_SERVER = "server"
SPAN_KIND_CLIENT = "client"
SPAN_KIND_PRODUCER = "producer"
SPAN_KIND_CONSUMER = "consumer"

# Span status
STATUS_UNSET = "unset"
STATUS_OK = "ok"
STATUS_ERROR = "error"

# Sampler types
SAMPLER_ALWAYS_ON = "always_on"
SAMPLER_ALWAYS_OFF = "always_off"
SAMPLER_RATIO = "ratio"
SAMPLER_PARENT_BASED = "parent_based"

# Exporter types
EXPORTER_OTLP = "otlp"
EXPORTER_JAEGER = "jaeger"
EXPORTER_ZIPKIN = "zipkin"
EXPORTER_CONSOLE = "console"
EXPORTER_NONE = "none"

# Default values
DEFAULT_SERVICE_NAME = "icyquant"
DEFAULT_SAMPLE_RATIO = 1.0
DEFAULT_MAX_SPANS = 10000
