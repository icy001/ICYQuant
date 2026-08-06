"""Observability telemetry for ICYQuant Service Mesh.

Provides ``ObservabilityTelemetry`` for structured logging of
observability events including traces, spans, policy evaluations,
anomalies, and runtime analyses.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ObservabilityTelemetry:
    """Records observability telemetry events."""

    def __init__(self, max_events: int = 5000) -> None:
        self._lock = threading.RLock()
        self._events: List[Dict[str, Any]] = []
        self._max_events = max_events

    def log_event(
        self,
        event_type: str,
        component: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            event = {
                "event_type": event_type,
                "component": component,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat(),
            }
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

    def log_trace(
        self,
        trace_id: str,
        operation: str,
        source: str = "",
        destination: str = "",
        duration_s: float = 0.0,
        success: bool = True,
    ) -> None:
        self.log_event(
            "trace",
            "trace_collector",
            {
                "trace_id": trace_id,
                "operation": operation,
                "source": source,
                "destination": destination,
                "duration_s": duration_s,
                "success": success,
            },
        )

    def log_span(
        self,
        span_id: str,
        trace_id: str,
        operation: str,
        duration_s: float = 0.0,
        success: bool = True,
    ) -> None:
        self.log_event(
            "span",
            "span_processor",
            {
                "span_id": span_id,
                "trace_id": trace_id,
                "operation": operation,
                "duration_s": duration_s,
                "success": success,
            },
        )

    def log_policy_eval(
        self,
        policy_id: str,
        result: str,
        principal: str = "",
        resource: str = "",
    ) -> None:
        self.log_event(
            "policy_eval",
            "policy_evaluator",
            {
                "policy_id": policy_id,
                "result": result,
                "principal": principal,
                "resource": resource,
            },
        )

    def log_anomaly(
        self,
        anomaly_type: str,
        target: str,
        severity: str = "warning",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.log_event(
            "anomaly",
            "anomaly_detector",
            {
                "anomaly_type": anomaly_type,
                "target": target,
                "severity": severity,
                "details": details or {},
            },
        )

    def log_slo_violation(
        self,
        slo_id: str,
        metric: str,
        expected: float,
        actual: float,
    ) -> None:
        self.log_event(
            "slo_violation",
            "slo",
            {
                "slo_id": slo_id,
                "metric": metric,
                "expected": expected,
                "actual": actual,
            },
        )

    def log_runtime_analysis(
        self,
        analysis_type: str,
        recommendations: List[str],
    ) -> None:
        self.log_event(
            "runtime_analysis",
            "runtime_analyzer",
            {
                "analysis_type": analysis_type,
                "recommendations": recommendations,
            },
        )

    def log_adaptive_adjustment(
        self,
        policy_id: str,
        adjustment: str,
        reason: str,
    ) -> None:
        self.log_event(
            "adaptive_adjustment",
            "adaptive_policy",
            {
                "policy_id": policy_id,
                "adjustment": adjustment,
                "reason": reason,
            },
        )

    def log_dashboard_request(
        self,
        endpoint: str,
        status: int = 200,
        duration_s: float = 0.0,
    ) -> None:
        self.log_event(
            "dashboard_request",
            "dashboard",
            {
                "endpoint": endpoint,
                "status": status,
                "duration_s": duration_s,
            },
        )

    def log_error(
        self,
        component: str,
        error_type: str,
        message: str,
    ) -> None:
        self.log_event(
            "error",
            component,
            {
                "error_type": error_type,
                "message": message,
            },
        )

    def get_events(
        self,
        event_type: Optional[str] = None,
        component: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            events = list(self._events)
        if event_type:
            events = [e for e in events if e["event_type"] == event_type]
        if component:
            events = [e for e in events if e["component"] == component]
        return events[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "event_count": len(self._events),
                "max_events": self._max_events,
            }

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
