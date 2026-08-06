"""Observability platform for ICYQuant Service Mesh.

Provides distributed tracing, metrics collection, access logging,
runtime policy evaluation, adaptive governance, SLO/SLI monitoring,
anomaly detection, runtime analysis, and dashboard API.
"""

from __future__ import annotations

# Events
from .events import ObservabilityEvent, ObservabilityEventPublisher

# Metrics
from .metrics import ObservabilityMetrics

# Telemetry
from .telemetry import ObservabilityTelemetry

# Health
from .health import ObservabilityHealth

# Diagnostics
from .diagnostics import ObservabilityDiagnostics

# Trace layer
from .trace_context import TraceContext, TraceContextManager
from .span_processor import (
    Span,
    SpanKind,
    SpanStatus,
    SpanProcessor,
    SpanSampler,
    SpanExporter,
    SamplingStrategy,
)
from .trace_collector import Trace, TraceCollector

# Metrics layer
from .metrics_collector import MeshMetricsCollector, MetricType, MetricPoint
from .metrics_aggregator import MetricsAggregator, RollingWindow, EWMA

# Log layer
from .access_log import AccessLogEntry, AccessLogger
from .log_pipeline import LogPipeline, LogFilter, LogStorage

# Policy layer
from .policy_repository import RuntimePolicy, RuntimePolicyRepository
from .policy_evaluator import PolicyEvaluator, PolicyType, EvaluationResult
from .adaptive_policy import (
    AdaptivePolicyEngine,
    AdaptiveRule,
    AdjustmentAction,
    AdjustmentRecord,
    AdjustmentSignal,
)

# Analytics layer
from .runtime_analyzer import RuntimeAnalyzer, AnalysisResult, AnalysisType
from .anomaly_detector import AnomalyDetector, Anomaly, AnomalyType, AnomalySeverity

# SLO/SLI layer
from .sli import SLI, SLICalculator, SLIType
from .slo import SLO, SLOMonitor, SLOStatus, ErrorBudget

# API layer
from .dashboard import DashboardProvider, DashboardView
from .api import ObservabilityAPI, APIRoute, APIResponse

# Scheduler
from .scheduler import ObservabilityScheduler, ObservabilityTask

# Orchestration
from .observability_manager import MeshObservability

__all__ = [
    # Events
    "ObservabilityEvent",
    "ObservabilityEventPublisher",
    # Metrics
    "ObservabilityMetrics",
    # Telemetry
    "ObservabilityTelemetry",
    # Health
    "ObservabilityHealth",
    # Diagnostics
    "ObservabilityDiagnostics",
    # Trace
    "TraceContext",
    "TraceContextManager",
    "Span",
    "SpanKind",
    "SpanStatus",
    "SpanProcessor",
    "SpanSampler",
    "SpanExporter",
    "SamplingStrategy",
    "Trace",
    "TraceCollector",
    # Metrics layer
    "MeshMetricsCollector",
    "MetricType",
    "MetricPoint",
    "MetricsAggregator",
    "RollingWindow",
    "EWMA",
    # Log
    "AccessLogEntry",
    "AccessLogger",
    "LogPipeline",
    "LogFilter",
    "LogStorage",
    # Policy
    "RuntimePolicy",
    "RuntimePolicyRepository",
    "PolicyEvaluator",
    "PolicyType",
    "EvaluationResult",
    "AdaptivePolicyEngine",
    "AdaptiveRule",
    "AdjustmentAction",
    "AdjustmentRecord",
    "AdjustmentSignal",
    # Analytics
    "RuntimeAnalyzer",
    "AnalysisResult",
    "AnalysisType",
    "AnomalyDetector",
    "Anomaly",
    "AnomalyType",
    "AnomalySeverity",
    # SLO/SLI
    "SLI",
    "SLICalculator",
    "SLIType",
    "SLO",
    "SLOMonitor",
    "SLOStatus",
    "ErrorBudget",
    # API
    "DashboardProvider",
    "DashboardView",
    "ObservabilityAPI",
    "APIRoute",
    "APIResponse",
    # Scheduler
    "ObservabilityScheduler",
    "ObservabilityTask",
    # Orchestration
    "MeshObservability",
]
