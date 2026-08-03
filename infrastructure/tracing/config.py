"""
Tracing configuration.
"""

from __future__ import annotations

from pydantic import BaseModel


class TracingConfig(BaseModel):
    """
    Tracing configuration.

    Controls distributed tracing behavior
    across the ICYQuant platform.

    Attributes:
        enabled: Whether tracing is enabled.
        service_name: Service name for traces.
        environment: Deployment environment.
        sample_ratio: Sampling ratio (0.0 - 1.0).
        exporter: Exporter type (otlp, jaeger, zipkin).
        max_spans_per_trace: Maximum spans per trace.
        max_attributes_per_span: Max attributes per span.
        max_events_per_span: Max events per span.
        trace_timeout: Trace timeout in seconds.
    """

    enabled: bool = True
    service_name: str = "icyquant"
    environment: str = "dev"
    sample_ratio: float = 1.0
    exporter: str = "otlp"
    max_spans_per_trace: int = 10000
    max_attributes_per_span: int = 128
    max_events_per_span: int = 128
    trace_timeout: float = 300.0
