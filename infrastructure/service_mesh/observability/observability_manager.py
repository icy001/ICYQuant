"""Observability manager for ICYQuant Service Mesh.

Provides ``MeshObservability`` as the unified entry point for the
observability platform, coordinating trace collection, metrics,
access logs, policy evaluation, runtime analytics, and adaptive
governance.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .access_log import AccessLogEntry, AccessLogger
from .adaptive_policy import AdaptivePolicyEngine, AdjustmentSignal
from .anomaly_detector import AnomalyDetector, Anomaly
from .api import ObservabilityAPI
from .dashboard import DashboardProvider
from .diagnostics import ObservabilityDiagnostics
from .events import ObservabilityEvent, ObservabilityEventPublisher
from .health import ObservabilityHealth
from .log_pipeline import LogPipeline
from .metrics import ObservabilityMetrics
from .metrics_aggregator import MetricsAggregator
from .metrics_collector import MeshMetricsCollector
from .policy_evaluator import PolicyEvaluator, PolicyType
from .policy_repository import RuntimePolicy, RuntimePolicyRepository
from .runtime_analyzer import RuntimeAnalyzer
from .scheduler import ObservabilityScheduler
from .sli import SLI, SLICalculator, SLIType
from .slo import SLO, SLOMonitor
from .span_processor import SpanProcessor
from .telemetry import ObservabilityTelemetry
from .trace_collector import TraceCollector
from .trace_context import TraceContext, TraceContextManager

logger = logging.getLogger(__name__)


class MeshObservability:
    """Unified observability entry point for the service mesh.

    Coordinates trace collection, metrics, access logs, policy
    evaluation, runtime analytics, and adaptive governance.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()

        # Infrastructure
        self._publisher = ObservabilityEventPublisher()
        self._metrics = ObservabilityMetrics()
        self._telemetry = ObservabilityTelemetry()
        self._health = ObservabilityHealth()
        self._diagnostics = ObservabilityDiagnostics()

        # Trace layer
        self._span_processor = SpanProcessor()
        self._trace_collector = TraceCollector(
            span_processor=self._span_processor,
        )

        # Metrics layer
        self._metrics_collector = MeshMetricsCollector()
        self._metrics_aggregator = MetricsAggregator()

        # Log layer
        self._access_logger = AccessLogger()
        self._log_pipeline = LogPipeline(access_logger=self._access_logger)

        # Policy layer
        self._policy_repository = RuntimePolicyRepository()
        self._policy_evaluator = PolicyEvaluator(repository=self._policy_repository)
        self._adaptive_engine = AdaptivePolicyEngine(repository=self._policy_repository)

        # Analytics layer
        self._runtime_analyzer = RuntimeAnalyzer()
        self._anomaly_detector = AnomalyDetector()

        # SLO/SLI layer
        self._sli_calculator = SLICalculator()
        self._slo_monitor = SLOMonitor(sli_calculator=self._sli_calculator)

        # API layer
        self._dashboard = DashboardProvider()
        self._api = ObservabilityAPI(dashboard=self._dashboard)

        # Scheduler
        self._scheduler = ObservabilityScheduler()

        # Wire data sources to dashboard
        self._wire_dashboard()

        # Wire health checks
        self._wire_health()

        # Wire scheduler tasks
        self._wire_scheduler()

        self._started = False

    def _wire_dashboard(self) -> None:
        self._dashboard.register_data_source("trace_collector", self._trace_collector)
        self._dashboard.register_data_source("metrics_collector", self._metrics_collector)
        self._dashboard.register_data_source("access_logger", self._access_logger)
        self._dashboard.register_data_source("policy_evaluator", self._policy_evaluator)
        self._dashboard.register_data_source("adaptive_policy", self._adaptive_engine)
        self._dashboard.register_data_source("runtime_analyzer", self._runtime_analyzer)
        self._dashboard.register_data_source("anomaly_detector", self._anomaly_detector)
        self._dashboard.register_data_source("slo_monitor", self._slo_monitor)
        self._dashboard.register_data_source("health", self._health)

    def _wire_health(self) -> None:
        self._health.register_check(
            "trace_collector", lambda: self._trace_collector.is_running
        )
        self._health.register_check(
            "metrics_collector", lambda: self._metrics_collector.is_running
        )
        self._health.register_check(
            "log_pipeline", lambda: self._log_pipeline.is_running
        )
        self._health.register_check(
            "policy_evaluator", lambda: self._policy_evaluator.is_running
        )
        self._health.register_check(
            "runtime_analyzer", lambda: self._runtime_analyzer.is_running
        )
        self._health.register_check(
            "anomaly_detector", lambda: self._anomaly_detector.is_running
        )
        self._health.register_check(
            "slo_monitor", lambda: self._slo_monitor.is_running
        )
        self._health.register_check(
            "dashboard", lambda: self._dashboard.is_running
        )

    def _wire_scheduler(self) -> None:
        self._scheduler.register_task(
            "policy_refresh",
            self._refresh_policies,
            interval_s=300.0,
            enabled=True,
        )
        self._scheduler.register_task(
            "metrics_flush",
            self._flush_metrics,
            interval_s=60.0,
            enabled=True,
        )
        self._scheduler.register_task(
            "trace_cleanup",
            self._cleanup_traces,
            interval_s=600.0,
            enabled=True,
        )
        self._scheduler.register_task(
            "slo_evaluation",
            self._evaluate_slos,
            interval_s=120.0,
            enabled=True,
        )
        self._scheduler.register_task(
            "anomaly_scan",
            self._scan_anomalies,
            interval_s=60.0,
            enabled=True,
        )

    def _refresh_policies(self) -> Dict[str, Any]:
        result = {"refreshed": True, "timestamp": datetime.utcnow().isoformat()}
        self._publisher.publish(ObservabilityEvent.POLICY_CHANGED, result)
        return result

    def _flush_metrics(self) -> Dict[str, Any]:
        result = self._metrics_collector.flush()
        self._metrics.increment_metrics_flush()
        self._publisher.publish(ObservabilityEvent.METRICS_FLUSHED, result)
        return result

    def _cleanup_traces(self) -> Dict[str, Any]:
        result = {"cleaned": True, "timestamp": datetime.utcnow().isoformat()}
        return result

    def _evaluate_slos(self) -> Dict[str, Any]:
        results = self._slo_monitor.evaluate_all()
        for result in results:
            if result["status"] == "violated":
                self._metrics.increment_slo_violation()
                self._telemetry.log_slo_violation(
                    result["slo_id"],
                    result["sli_type"],
                    result["target"],
                    result["current_value"],
                )
                self._publisher.publish(
                    ObservabilityEvent.SLO_VIOLATION,
                    {"slo_id": result["slo_id"], "value": result["current_value"]},
                )
        return {"evaluated": len(results)}

    def _scan_anomalies(self) -> Dict[str, Any]:
        adjustments = self._adaptive_engine.evaluate()
        for adj in adjustments:
            self._telemetry.log_adaptive_adjustment(
                adj.rule_id,
                adj.action,
                adj.reason,
            )
        return {"adjustments": len(adjustments)}

    # --- Properties ---

    @property
    def trace_collector(self) -> TraceCollector:
        return self._trace_collector

    @property
    def span_processor(self) -> SpanProcessor:
        return self._span_processor

    @property
    def metrics_collector(self) -> MeshMetricsCollector:
        return self._metrics_collector

    @property
    def metrics_aggregator(self) -> MetricsAggregator:
        return self._metrics_aggregator

    @property
    def access_logger(self) -> AccessLogger:
        return self._access_logger

    @property
    def log_pipeline(self) -> LogPipeline:
        return self._log_pipeline

    @property
    def policy_repository(self) -> RuntimePolicyRepository:
        return self._policy_repository

    @property
    def policy_evaluator(self) -> PolicyEvaluator:
        return self._policy_evaluator

    @property
    def adaptive_engine(self) -> AdaptivePolicyEngine:
        return self._adaptive_engine

    @property
    def runtime_analyzer(self) -> RuntimeAnalyzer:
        return self._runtime_analyzer

    @property
    def anomaly_detector(self) -> AnomalyDetector:
        return self._anomaly_detector

    @property
    def slo_monitor(self) -> SLOMonitor:
        return self._slo_monitor

    @property
    def sli_calculator(self) -> SLICalculator:
        return self._sli_calculator

    @property
    def dashboard(self) -> DashboardProvider:
        return self._dashboard

    @property
    def api(self) -> ObservabilityAPI:
        return self._api

    @property
    def scheduler(self) -> ObservabilityScheduler:
        return self._scheduler

    @property
    def metrics(self) -> ObservabilityMetrics:
        return self._metrics

    @property
    def telemetry(self) -> ObservabilityTelemetry:
        return self._telemetry

    @property
    def health(self) -> ObservabilityHealth:
        return self._health

    @property
    def diagnostics(self) -> ObservabilityDiagnostics:
        return self._diagnostics

    @property
    def event_publisher(self) -> ObservabilityEventPublisher:
        return self._publisher

    @property
    def is_running(self) -> bool:
        return self._started

    # --- Lifecycle ---

    async def initialize(self) -> Dict[str, Any]:
        """Initialize the observability platform."""
        with self._lock:
            if self._started:
                return {"success": False, "error": "Already started"}

        self._trace_collector.start()
        self._metrics_collector.start()
        self._log_pipeline.start()
        self._policy_evaluator.start()
        self._adaptive_engine.start()
        self._runtime_analyzer.start()
        self._anomaly_detector.start()
        self._slo_monitor.start()
        self._dashboard.start()
        self._api.start()
        await self._scheduler.start()

        self._started = True
        self._telemetry.log_event("initialized", "observability_manager")
        logger.info("MeshObservability initialized")
        return {"success": True, "started": True}

    async def shutdown(self) -> Dict[str, Any]:
        with self._lock:
            if not self._started:
                return {"success": False, "error": "Not started"}

        await self._scheduler.stop()
        self._api.stop()
        self._dashboard.stop()
        self._slo_monitor.stop()
        self._anomaly_detector.stop()
        self._runtime_analyzer.stop()
        self._adaptive_engine.stop()
        self._policy_evaluator.stop()
        self._log_pipeline.stop()
        self._metrics_collector.stop()
        self._trace_collector.stop()

        self._started = False
        self._telemetry.log_event("shutdown", "observability_manager")
        logger.info("MeshObservability shutdown")
        return {"success": True, "started": False}

    # --- Operations ---

    def start_trace(
        self,
        operation: str = "",
        source: str = "",
        destination: str = "",
    ) -> Any:
        trace = self._trace_collector.start_trace(
            operation=operation,
            source=source,
            destination=destination,
        )
        self._metrics.increment_trace({"operation": operation})
        self._telemetry.log_trace(
            trace.trace_id, operation, source, destination, 0.0, True
        )
        self._diagnostics.register_trace(
            trace.trace_id,
            {"operation": operation, "source": source, "destination": destination},
        )
        self._publisher.publish(
            ObservabilityEvent.TRACE_STARTED,
            {"trace_id": trace.trace_id, "operation": operation},
        )
        return trace

    def complete_trace(
        self,
        trace_id: str,
        success: bool = True,
        error: Optional[str] = None,
    ) -> Any:
        trace = self._trace_collector.complete_trace(
            trace_id, success=success, error=error
        )
        if trace:
            self._telemetry.log_trace(
                trace_id,
                trace.operation,
                trace.source,
                trace.destination,
                trace.duration_s,
                success,
            )
            self._diagnostics.unregister_trace(trace_id)
            self._publisher.publish(
                ObservabilityEvent.TRACE_COMPLETED,
                {"trace_id": trace_id, "success": success, "duration_s": trace.duration_s},
            )
        return trace

    def record_access(
        self,
        source: str,
        destination: str,
        method: str = "GET",
        path: str = "/",
        status_code: int = 200,
        latency_ms: float = 0.0,
        retry_count: int = 0,
        trace_id: str = "",
        identity: str = "",
    ) -> AccessLogEntry:
        entry = self._access_logger.log_request(
            source=source,
            destination=destination,
            method=method,
            path=path,
            status_code=status_code,
            latency_ms=latency_ms,
            retry_count=retry_count,
            trace_id=trace_id,
            identity=identity,
        )
        self._metrics.increment_access_log({"source": source})
        self._metrics_collector.record_traffic(destination)
        self._metrics_collector.record_latency(destination, latency_ms)
        if status_code >= 400:
            self._metrics_collector.record_error(destination)
        if retry_count > 0:
            self._metrics_collector.record_retry(destination, retry_count)
        self._metrics_aggregator.record(
            "latency_ms", latency_ms,
            service=destination,
        )
        self._slo_monitor.record_request(destination, status_code < 400, latency_ms)
        self._runtime_analyzer.record_traffic(
            source, destination, latency_ms, status_code < 400
        )
        if status_code >= 400:
            self._anomaly_detector.record_error(destination, True)
        else:
            self._anomaly_detector.record_error(destination, False)
        self._anomaly_detector.record_latency(destination, latency_ms)
        self._telemetry.log_event("access_logged", "access_logger", entry.to_dict())
        return entry

    def register_policy(self, policy: RuntimePolicy) -> None:
        self._policy_evaluator.register_policy(policy)
        self._diagnostics.record_policy_evaluation(
            policy.policy_id, "system", "registered"
        )
        self._publisher.publish(
            ObservabilityEvent.POLICY_CHANGED,
            {"policy_id": policy.policy_id, "action": "registered"},
        )

    def register_slo(self, slo: SLO) -> None:
        self._slo_monitor.register_slo(slo)
        self._publisher.publish(
            ObservabilityEvent.POLICY_CHANGED,
            {"slo_id": slo.slo_id, "action": "registered"},
        )

    def update_signals(self, signals: Dict[str, float]) -> None:
        self._adaptive_engine.update_signals(signals)
        adjustments = self._adaptive_engine.evaluate()
        for adj in adjustments:
            self._telemetry.log_adaptive_adjustment(
                adj.rule_id, adj.action, adj.reason
            )
            self._publisher.publish(
                ObservabilityEvent.ADAPTIVE_ADJUSTMENT,
                adj.to_dict(),
            )

    def analyze_runtime(self) -> List[Any]:
        results = self._runtime_analyzer.analyze_all()
        for result in results:
            self._metrics.increment_runtime_analysis({"type": result.analysis_type})
            self._telemetry.log_runtime_analysis(
                result.analysis_type, result.recommendations
            )
            self._diagnostics.record_analysis(
                result.analysis_type, result.recommendations
            )
        self._publisher.publish(
            ObservabilityEvent.RUNTIME_ANALYZED,
            {"result_count": len(results)},
        )
        return results

    async def health_check(self) -> Dict[str, Any]:
        return await self._health.check()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "started": self._started,
            "trace": self._trace_collector.get_stats(),
            "metrics": self._metrics.get_summary(),
            "metrics_collector": self._metrics_collector.get_stats(),
            "access_logger": self._access_logger.get_stats(),
            "log_pipeline": self._log_pipeline.get_stats(),
            "policy_evaluator": self._policy_evaluator.get_stats(),
            "adaptive_engine": self._adaptive_engine.get_stats(),
            "runtime_analyzer": self._runtime_analyzer.get_stats(),
            "anomaly_detector": self._anomaly_detector.get_stats(),
            "slo_monitor": self._slo_monitor.get_stats(),
            "dashboard": self._dashboard.get_stats(),
            "scheduler": self._scheduler.get_stats(),
            "diagnostics": self._diagnostics.get_snapshot(),
        }
