"""Diagnostics for the observability platform.

Provides ``ObservabilityDiagnostics`` for in-depth state inspection
of all observability components.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ObservabilityDiagnostics:
    """Diagnostics manager for observability components."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._trace_table: Dict[str, Dict[str, Any]] = {}
        self._policy_evaluations: List[Dict[str, Any]] = []
        self._anomalies: List[Dict[str, Any]] = []
        self._component_status: Dict[str, Dict[str, Any]] = {}
        self._analysis_history: List[Dict[str, Any]] = []

    def register_trace(self, trace_id: str, info: Dict[str, Any]) -> None:
        with self._lock:
            self._trace_table[trace_id] = {
                "trace_id": trace_id,
                "registered_at": datetime.utcnow().isoformat(),
                **info,
            }

    def unregister_trace(self, trace_id: str) -> None:
        with self._lock:
            self._trace_table.pop(trace_id, None)

    def record_policy_evaluation(
        self,
        policy_id: str,
        principal: str,
        result: str,
    ) -> None:
        with self._lock:
            self._policy_evaluations.append(
                {
                    "policy_id": policy_id,
                    "principal": principal,
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            if len(self._policy_evaluations) > 500:
                self._policy_evaluations = self._policy_evaluations[-500:]

    def record_anomaly(
        self,
        anomaly_type: str,
        target: str,
        severity: str = "warning",
    ) -> None:
        with self._lock:
            self._anomalies.append(
                {
                    "anomaly_type": anomaly_type,
                    "target": target,
                    "severity": severity,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            if len(self._anomalies) > 200:
                self._anomalies = self._anomalies[-200:]

    def record_analysis(
        self,
        analysis_type: str,
        recommendations: List[str],
    ) -> None:
        with self._lock:
            self._analysis_history.append(
                {
                    "analysis_type": analysis_type,
                    "recommendations": recommendations,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            if len(self._analysis_history) > 100:
                self._analysis_history = self._analysis_history[-100:]

    def set_component_status(
        self,
        component: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            self._component_status[component] = {
                "status": status,
                "details": details or {},
                "updated_at": datetime.utcnow().isoformat(),
            }

    def get_component_status(
        self, component: str
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._component_status.get(component)

    def get_trace_table(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._trace_table.values())

    def get_policy_evaluations(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._policy_evaluations)

    def get_anomalies(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._anomalies)

    def get_analysis_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._analysis_history)

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "trace_count": len(self._trace_table),
                "policy_evaluation_count": len(self._policy_evaluations),
                "anomaly_count": len(self._anomalies),
                "analysis_count": len(self._analysis_history),
                "component_count": len(self._component_status),
                "components": dict(self._component_status),
            }

    def get_stats(self) -> Dict[str, Any]:
        return self.get_snapshot()

    def clear(self) -> None:
        with self._lock:
            self._trace_table.clear()
            self._policy_evaluations.clear()
            self._anomalies.clear()
            self._component_status.clear()
            self._analysis_history.clear()
