"""Dashboard API for ICYQuant Service Mesh observability.

Provides ``DashboardProvider`` for serving mesh overview, topology,
traffic, trace, policy, security, and health data to web consoles.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DashboardView(str):
    """Dashboard view types."""

    OVERVIEW = "overview"
    TOPOLOGY = "topology"
    TRAFFIC = "traffic"
    TRACE = "trace"
    POLICY = "policy"
    SECURITY = "security"
    HEALTH = "health"
    SLO = "slo"
    ANOMALY = "anomaly"
    ANALYSIS = "analysis"


class DashboardProvider:
    """Provides dashboard data for web console."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data_sources: Dict[str, Any] = {}
        self._request_count = 0
        self._view_counts: Dict[str, int] = {}
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started

    def start(self) -> None:
        self._started = True
        logger.info("Dashboard provider started")

    def stop(self) -> None:
        self._started = False
        logger.info("Dashboard provider stopped")

    def register_data_source(self, name: str, source: Any) -> None:
        with self._lock:
            self._data_sources[name] = source

    def unregister_data_source(self, name: str) -> bool:
        with self._lock:
            if name in self._data_sources:
                del self._data_sources[name]
                return True
            return False

    def get_overview(self) -> Dict[str, Any]:
        self._record_request(DashboardView.OVERVIEW)
        result: Dict[str, Any] = {
            "view": "overview",
            "timestamp": datetime.utcnow().isoformat(),
            "mesh": {},
            "services": [],
            "slo_count": 0,
            "anomaly_count": 0,
        }
        with self._lock:
            sources = dict(self._data_sources)

        if "trace_collector" in sources:
            result["mesh"]["traces"] = sources["trace_collector"].get_stats()
        if "metrics_collector" in sources:
            result["mesh"]["metrics"] = sources["metrics_collector"].get_stats()
        if "access_logger" in sources:
            result["mesh"]["access_logs"] = sources["access_logger"].get_stats()
        if "slo_monitor" in sources:
            slo_stats = sources["slo_monitor"].get_stats()
            result["slo_count"] = slo_stats.get("slo_count", 0)
            result["mesh"]["slo"] = slo_stats
        if "anomaly_detector" in sources:
            anom_stats = sources["anomaly_detector"].get_stats()
            result["anomaly_count"] = anom_stats.get("anomaly_count", 0)
            result["mesh"]["anomalies"] = anom_stats
        if "policy_evaluator" in sources:
            result["mesh"]["policies"] = sources["policy_evaluator"].get_stats()
        return result

    def get_topology(self) -> Dict[str, Any]:
        self._record_request(DashboardView.TOPOLOGY)
        with self._lock:
            sources = dict(self._data_sources)

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        if "runtime_analyzer" in sources:
            dep_result = sources["runtime_analyzer"].analyze_dependencies()
            for finding in dep_result.findings:
                nodes.append({
                    "id": finding["service"],
                    "label": finding["service"],
                    "dependency_count": finding["dependency_count"],
                })
                for dep in finding.get("depends_on", []):
                    edges.append({
                        "source": finding["service"],
                        "target": dep,
                    })
        return {
            "view": "topology",
            "timestamp": datetime.utcnow().isoformat(),
            "nodes": nodes,
            "edges": edges,
        }

    def get_traffic(self) -> Dict[str, Any]:
        self._record_request(DashboardView.TRAFFIC)
        with self._lock:
            sources = dict(self._data_sources)
        result: Dict[str, Any] = {
            "view": "traffic",
            "timestamp": datetime.utcnow().isoformat(),
            "requests": {},
            "top_services": [],
        }
        if "metrics_collector" in sources:
            result["requests"] = sources["metrics_collector"].get_stats()
        if "access_logger" in sources:
            stats = sources["access_logger"].get_stats()
            result["access_logs"] = stats
            result["top_services"] = []
        return result

    def get_traces(self, limit: int = 20) -> Dict[str, Any]:
        self._record_request(DashboardView.TRACE)
        with self._lock:
            sources = dict(self._data_sources)
        traces: List[Dict[str, Any]] = []
        if "trace_collector" in sources:
            recent = sources["trace_collector"].get_completed_traces(limit=limit)
            traces = [t.to_dict() for t in recent]
        return {
            "view": "trace",
            "timestamp": datetime.utcnow().isoformat(),
            "traces": traces,
            "count": len(traces),
        }

    def get_policies(self) -> Dict[str, Any]:
        self._record_request(DashboardView.POLICY)
        with self._lock:
            sources = dict(self._data_sources)
        result: Dict[str, Any] = {
            "view": "policy",
            "timestamp": datetime.utcnow().isoformat(),
            "policies": [],
            "adaptive": {},
        }
        if "policy_evaluator" in sources:
            result["evaluator"] = sources["policy_evaluator"].get_stats()
        if "adaptive_policy" in sources:
            result["adaptive"] = sources["adaptive_policy"].get_stats()
        return result

    def get_security(self) -> Dict[str, Any]:
        self._record_request(DashboardView.SECURITY)
        return {
            "view": "security",
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_health(self) -> Dict[str, Any]:
        self._record_request(DashboardView.HEALTH)
        with self._lock:
            sources = dict(self._data_sources)
        if "health" in sources:
            return sources["health"]
        return {
            "view": "health",
            "timestamp": datetime.utcnow().isoformat(),
            "healthy": True,
        }

    def get_slo(self) -> Dict[str, Any]:
        self._record_request(DashboardView.SLO)
        with self._lock:
            sources = dict(self._data_sources)
        slos: List[Dict[str, Any]] = []
        if "slo_monitor" in sources:
            slos = [slo.evaluate() for slo in sources["slo_monitor"].list_slos()]
        return {
            "view": "slo",
            "timestamp": datetime.utcnow().isoformat(),
            "slos": slos,
            "count": len(slos),
        }

    def get_anomalies(self, limit: int = 50) -> Dict[str, Any]:
        self._record_request(DashboardView.ANOMALY)
        with self._lock:
            sources = dict(self._data_sources)
        anomalies: List[Dict[str, Any]] = []
        if "anomaly_detector" in sources:
            anomalies = [a.to_dict() for a in sources["anomaly_detector"].get_anomalies(limit=limit)]
        return {
            "view": "anomaly",
            "timestamp": datetime.utcnow().isoformat(),
            "anomalies": anomalies,
            "count": len(anomalies),
        }

    def get_analysis(self) -> Dict[str, Any]:
        self._record_request(DashboardView.ANALYSIS)
        with self._lock:
            sources = dict(self._data_sources)
        analyses: List[Dict[str, Any]] = []
        if "runtime_analyzer" in sources:
            for result in sources["runtime_analyzer"].analyze_all():
                analyses.append(result.to_dict())
        return {
            "view": "analysis",
            "timestamp": datetime.utcnow().isoformat(),
            "analyses": analyses,
            "count": len(analyses),
        }

    def get_view(self, view: str, **kwargs: Any) -> Dict[str, Any]:
        dispatch = {
            DashboardView.OVERVIEW: self.get_overview,
            DashboardView.TOPOLOGY: self.get_topology,
            DashboardView.TRAFFIC: self.get_traffic,
            DashboardView.TRACE: lambda: self.get_traces(kwargs.get("limit", 20)),
            DashboardView.POLICY: self.get_policies,
            DashboardView.SECURITY: self.get_security,
            DashboardView.HEALTH: self.get_health,
            DashboardView.SLO: self.get_slo,
            DashboardView.ANOMALY: lambda: self.get_anomalies(kwargs.get("limit", 50)),
            DashboardView.ANALYSIS: self.get_analysis,
        }
        fn = dispatch.get(view, self.get_overview)
        return fn()

    def _record_request(self, view: str) -> None:
        with self._lock:
            self._request_count += 1
            self._view_counts[view] = self._view_counts.get(view, 0) + 1

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._started,
                "request_count": self._request_count,
                "view_counts": dict(self._view_counts),
                "data_source_count": len(self._data_sources),
            }
