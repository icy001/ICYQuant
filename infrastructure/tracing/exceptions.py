"""
Tracing exceptions.
"""

from __future__ import annotations


class TracingError(Exception):
    """Base tracing exception."""


class TracerError(TracingError):
    """Tracer error."""


class SpanError(TracingError):
    """Span error."""


class TraceError(TracingError):
    """Trace error."""


class PropagatorError(TracingError):
    """Propagator error."""


class SamplerError(TracingError):
    """Sampler error."""


class RegistryError(TracingError):
    """Registry error."""


class ConfigError(TracingError):
    """Configuration error."""


class ExporterError(TracingError):
    """Exporter error."""
