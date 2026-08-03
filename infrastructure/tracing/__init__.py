"""
Distributed tracing infrastructure.

Provides comprehensive distributed tracing
for the ICYQuant platform, enabling end-to-end
visibility across service boundaries.

Components:
- TracingConfig: Configuration
- SpanModel / TraceModel: Data models
- Tracer: Span creation and management
- TraceManager: Context management
- SpanFactory / TraceFactory: Model creation
- Samplers: Sampling strategies
- TracePropagator: Cross-service propagation
- ICYTracePropagator: W3C Trace Context + Baggage
- TraceFormatter: Output formatting
- TraceRegistry: Trace lifecycle management
- TracingHealth: Health monitoring
- TracingSDK: OpenTelemetry SDK integration
- ICYTracerProvider: Unified TracerProvider
- Resource management: OpenTelemetry Resource
- ProcessorFactory: Span processor factory
- BaggageManager: Baggage context management
- InstrumentationManager: Auto-instrumentation
- TracePipeline: Export pipeline (batch/retry/compress)
- TraceMetrics: Pipeline metrics
- TraceDiagnostics: Pipeline diagnostics
- Exporters: OTLP, Jaeger, Tempo, Zipkin, Console
- TracingService: Unified service entry point
- TracingBootstrap: One-click initialization
- TracingLifecycle: Startup/reload/shutdown management
- TracingMonitoring: Metrics collection
- TracingScheduler: Background maintenance
- TracingTelemetry: Unified observability
- DIContainer: Dependency injection

Usage:
    from infrastructure.tracing import TracingBootstrap, TracingConfig

    bootstrap = TracingBootstrap(config=TracingConfig())
    await bootstrap.startup()
    # ... application runs ...
    await bootstrap.shutdown()
"""

from .config import TracingConfig
from .constants import (
    EXPORTER_CONSOLE,
    EXPORTER_JAEGER,
    EXPORTER_NONE,
    EXPORTER_OTLP,
    EXPORTER_ZIPKIN,
    PARENT_SPAN_HEADER,
    SAMPLED_HEADER,
    SAMPLER_ALWAYS_OFF,
    SAMPLER_ALWAYS_ON,
    SAMPLER_PARENT_BASED,
    SAMPLER_RATIO,
    SPAN_HEADER,
    SPAN_KIND_CLIENT,
    SPAN_KIND_CONSUMER,
    SPAN_KIND_INTERNAL,
    SPAN_KIND_PRODUCER,
    SPAN_KIND_SERVER,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_UNSET,
    TRACE_HEADER,
)
from .context import (
    clear_trace,
    current_span,
    current_trace,
    set_span,
    set_trace,
)
from .exceptions import (
    ConfigError,
    ExporterError,
    PropagatorError,
    RegistryError,
    SamplerError,
    SpanError,
    TraceError,
    TracerError,
    TracingError,
)
from .formatter import TraceFormatter
from .health import TracingHealth
from .manager import TraceManager
from .models import (
    SpanEvent,
    SpanKind,
    SpanModel,
    SpanStatus,
    TraceModel,
)
from .propagator import ICYTracePropagator, TracePropagator
from .registry import TraceRegistry
from .sampler import (
    AlwaysOffSampler,
    AlwaysOnSampler,
    ParentBasedSampler,
    RatioSampler,
    Sampler,
)
from .span import SpanFactory
from .trace import TraceFactory
from .trace_id import TraceIdGenerator
from .tracer import SpanContextManager, Tracer

# ── OpenTelemetry SDK Integration ──

from .baggage import BaggageManager
from .instrumentation import (
    EventBusInstrumentation,
    FastAPIInstrumentation,
    gRPCInstrumentation,
    HTTPXInstrumentation,
    Instrumentation,
    InstrumentationManager,
    KafkaInstrumentation,
    RedisInstrumentation,
    SQLAlchemyInstrumentation,
)
from .processor import ProcessorFactory
from .provider import ICYTracerProvider
from .resource import build_resource, get_default_attributes
from .sdk import TracingSDK

# ── Export Pipeline (Part 2.4) ──

from .diagnostics import TraceDiagnostics
from .exporters import (
    ConsoleExporter,
    ExportManager,
    ExporterFactory,
    JaegerExporter,
    OTLPgRPCExporter,
    OTLPHTTPExporter,
    TempoExporter,
    TraceExporter,
    ZipkinExporter,
)
from .metrics import TraceMetrics
from .pipeline import TracePipeline
from .processor import (
    BatchProcessor,
    CompressionManager,
    RetryPolicy,
    SpanBuffer,
    SpanQueue,
    TimeoutController,
)

# ── Bootstrap & Integration (Part 2.5) ──

from .bootstrap import TracingBootstrap
from .container import DIContainer, register_tracing
from .lifecycle import TracingLifecycle
from .monitoring import TracingMonitoring
from .scheduler import TracingScheduler
from .service import TracingService
from .telemetry import TracingTelemetry

__all__ = [
    # Config
    "TracingConfig",
    # Constants
    "TRACE_HEADER",
    "SPAN_HEADER",
    "PARENT_SPAN_HEADER",
    "SAMPLED_HEADER",
    "SPAN_KIND_INTERNAL",
    "SPAN_KIND_SERVER",
    "SPAN_KIND_CLIENT",
    "SPAN_KIND_PRODUCER",
    "SPAN_KIND_CONSUMER",
    "STATUS_UNSET",
    "STATUS_OK",
    "STATUS_ERROR",
    "SAMPLER_ALWAYS_ON",
    "SAMPLER_ALWAYS_OFF",
    "SAMPLER_RATIO",
    "SAMPLER_PARENT_BASED",
    "EXPORTER_OTLP",
    "EXPORTER_JAEGER",
    "EXPORTER_ZIPKIN",
    "EXPORTER_CONSOLE",
    "EXPORTER_NONE",
    # Models
    "SpanModel",
    "SpanEvent",
    "SpanKind",
    "SpanStatus",
    "TraceModel",
    # Context
    "current_trace",
    "current_span",
    "set_trace",
    "set_span",
    "clear_trace",
    # Manager
    "TraceManager",
    # Factories
    "SpanFactory",
    "TraceFactory",
    "TraceIdGenerator",
    # Tracer
    "Tracer",
    "SpanContextManager",
    # Samplers
    "Sampler",
    "AlwaysOnSampler",
    "AlwaysOffSampler",
    "RatioSampler",
    "ParentBasedSampler",
    # Propagator
    "TracePropagator",
    "ICYTracePropagator",
    # Formatter
    "TraceFormatter",
    # Registry
    "TraceRegistry",
    # Health
    "TracingHealth",
    # OpenTelemetry SDK
    "TracingSDK",
    "ICYTracerProvider",
    "ProcessorFactory",
    "build_resource",
    "get_default_attributes",
    "BaggageManager",
    "InstrumentationManager",
    "Instrumentation",
    "FastAPIInstrumentation",
    "SQLAlchemyInstrumentation",
    "RedisInstrumentation",
    "KafkaInstrumentation",
    "HTTPXInstrumentation",
    "gRPCInstrumentation",
    "EventBusInstrumentation",
    # Export Pipeline (Part 2.4)
    "TracePipeline",
    "TraceMetrics",
    "TraceDiagnostics",
    "TraceExporter",
    "ConsoleExporter",
    "OTLPgRPCExporter",
    "OTLPHTTPExporter",
    "JaegerExporter",
    "TempoExporter",
    "ZipkinExporter",
    "ExportManager",
    "ExporterFactory",
    "BatchProcessor",
    "SpanQueue",
    "RetryPolicy",
    "CompressionManager",
    "TimeoutController",
    "SpanBuffer",
    # Bootstrap & Integration (Part 2.5)
    "TracingService",
    "TracingBootstrap",
    "TracingLifecycle",
    "TracingMonitoring",
    "TracingScheduler",
    "TracingTelemetry",
    "DIContainer",
    "register_tracing",
    # Exceptions
    "TracingError",
    "TracerError",
    "SpanError",
    "TraceError",
    "PropagatorError",
    "SamplerError",
    "RegistryError",
    "ConfigError",
    "ExporterError",
]
