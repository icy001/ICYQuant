"""Runtime analyzer for ICYQuant Service Mesh.

Provides ``RuntimeAnalyzer`` for analyzing traffic patterns, hot
services, dependencies, failure chains, and resource usage,
producing optimization recommendations.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class AnalysisType(str):
    """Types of runtime analysis."""

    TRAFFIC_PATTERN = "traffic_pattern"
    HOT_SERVICE = "hot_service"
    DEPENDENCY = "dependency"
    FAILURE_CHAIN = "failure_chain"
    RESOURCE_USAGE = "resource_usage"


class AnalysisResult:
    """Result of a runtime analysis."""

    def __init__(
        self,
        analysis_type: str,
        title: str = "",
        findings: Optional[List[Dict[str, Any]]] = None,
        recommendations: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.analysis_type = analysis_type
        self.title = title
        self.findings = findings or []
        self.recommendations = recommendations or []
        self.details = details or {}
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_type": self.analysis_type,
            "title": self.title,
            "findings": list(self.findings),
            "recommendations": list(self.recommendations),
            "details": dict(self.details),
            "timestamp": self.timestamp.isoformat(),
        }


class RuntimeAnalyzer:
    """Analyzes runtime patterns and produces recommendations."""

    def __init__(self, max_history: int = 500) -> None:
        self._max_history = max_history
        self._lock = threading.RLock()
        self._service_traffic: Dict[str, int] = defaultdict(int)
        self._service_errors: Dict[str, int] = defaultdict(int)
        self._service_latency: Dict[str, List[float]] = defaultdict(list)
        self._dependencies: Dict[str, Set[str]] = defaultdict(set)
        self._failure_chains: List[Dict[str, Any]] = []
        self._resource_usage: Dict[str, Dict[str, float]] = {}
        self._history: List[AnalysisResult] = []
        self._analysis_count = 0
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started

    def start(self) -> None:
        self._started = True
        logger.info("Runtime analyzer started")

    def stop(self) -> None:
        self._started = False
        logger.info("Runtime analyzer stopped")

    def record_traffic(self, source: str, destination: str, latency_ms: float = 0.0, success: bool = True) -> None:
        with self._lock:
            self._service_traffic[source] += 1
            self._service_traffic[destination] += 1
            self._dependencies[source].add(destination)
            if not success:
                self._service_errors[source] += 1
                self._service_errors[destination] += 1
                self._failure_chains.append({
                    "source": source,
                    "destination": destination,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                if len(self._failure_chains) > 200:
                    self._failure_chains = self._failure_chains[-200:]
            if latency_ms > 0:
                self._service_latency[destination].append(latency_ms)
                if len(self._service_latency[destination]) > 1000:
                    self._service_latency[destination] = self._service_latency[destination][-1000:]

    def record_resource(self, service: str, cpu: float = 0.0, memory: float = 0.0) -> None:
        with self._lock:
            self._resource_usage[service] = {"cpu": cpu, "memory": memory}

    def analyze_traffic_pattern(self) -> AnalysisResult:
        """Analyze traffic patterns across services."""
        with self._lock:
            traffic = dict(self._service_traffic)

        if not traffic:
            return AnalysisResult(
                AnalysisType.TRAFFIC_PATTERN,
                title="Traffic Pattern Analysis",
                findings=[],
                recommendations=["No traffic data available"],
            )

        total = sum(traffic.values())
        sorted_services = sorted(traffic.items(), key=lambda x: x[1], reverse=True)
        findings = [
            {
                "service": svc,
                "request_count": count,
                "percentage": count / total * 100 if total > 0 else 0,
            }
            for svc, count in sorted_services[:10]
        ]
        recommendations = []
        if sorted_services:
            top_service, top_count = sorted_services[0]
            if total > 0 and top_count / total > 0.5:
                recommendations.append(
                    f"Service '{top_service}' handles {top_count / total * 100:.1f}% "
                    f"of traffic - consider load balancing"
                )
        if not recommendations:
            recommendations.append("Traffic distribution looks healthy")

        result = AnalysisResult(
            AnalysisType.TRAFFIC_PATTERN,
            title="Traffic Pattern Analysis",
            findings=findings,
            recommendations=recommendations,
            details={"total_requests": total, "service_count": len(traffic)},
        )
        self._record_analysis(result)
        return result

    def analyze_hot_services(self) -> AnalysisResult:
        """Identify hot services with high traffic and latency."""
        with self._lock:
            traffic = dict(self._service_traffic)
            latency = {
                svc: sum(vals) / len(vals) if vals else 0
                for svc, vals in self._service_latency.items()
            }
            errors = dict(self._service_errors)

        hot_services = []
        for svc in traffic:
            svc_traffic = traffic[svc]
            svc_latency = latency.get(svc, 0)
            svc_errors = errors.get(svc, 0)
            error_rate = svc_errors / svc_traffic if svc_traffic > 0 else 0
            if svc_traffic > 1000 or svc_latency > 1000 or error_rate > 0.05:
                hot_services.append({
                    "service": svc,
                    "traffic": svc_traffic,
                    "avg_latency_ms": svc_latency,
                    "error_rate": error_rate,
                    "is_hot": True,
                })
        hot_services.sort(key=lambda x: x["traffic"], reverse=True)

        recommendations = []
        for svc in hot_services[:5]:
            if svc["error_rate"] > 0.05:
                recommendations.append(
                    f"Service '{svc['service']}' has high error rate ({svc['error_rate']:.1%}) - investigate"
                )
            if svc["avg_latency_ms"] > 1000:
                recommendations.append(
                    f"Service '{svc['service']}' has high latency ({svc['avg_latency_ms']:.0f}ms) - optimize"
                )
        if not recommendations:
            recommendations.append("No hot services detected")

        result = AnalysisResult(
            AnalysisType.HOT_SERVICE,
            title="Hot Service Analysis",
            findings=hot_services[:10],
            recommendations=recommendations,
            details={"hot_service_count": len(hot_services)},
        )
        self._record_analysis(result)
        return result

    def analyze_dependencies(self) -> AnalysisResult:
        """Analyze service dependency graph."""
        with self._lock:
            deps = {svc: list(targets) for svc, targets in self._dependencies.items()}

        findings = []
        for source, targets in deps.items():
            findings.append({
                "service": source,
                "depends_on": targets,
                "dependency_count": len(targets),
            })
        findings.sort(key=lambda x: x["dependency_count"], reverse=True)

        recommendations = []
        for f in findings[:5]:
            if f["dependency_count"] > 5:
                recommendations.append(
                    f"Service '{f['service']}' has {f['dependency_count']} dependencies - consider simplifying"
                )
        if not recommendations:
            recommendations.append("Dependency graph looks healthy")

        result = AnalysisResult(
            AnalysisType.DEPENDENCY,
            title="Dependency Analysis",
            findings=findings,
            recommendations=recommendations,
            details={"service_count": len(deps), "total_dependencies": sum(len(v) for v in deps.values())},
        )
        self._record_analysis(result)
        return result

    def analyze_failure_chains(self) -> AnalysisResult:
        """Analyze failure chains and cascading failures."""
        with self._lock:
            chains = list(self._failure_chains)

        if not chains:
            result = AnalysisResult(
                AnalysisType.FAILURE_CHAIN,
                title="Failure Chain Analysis",
                findings=[],
                recommendations=["No failures detected"],
            )
            self._record_analysis(result)
            return result

        failure_by_pair: Dict[Tuple[str, str], int] = defaultdict(int)
        for chain in chains:
            pair = (chain["source"], chain["destination"])
            failure_by_pair[pair] += 1

        findings = [
            {
                "source": pair[0],
                "destination": pair[1],
                "failure_count": count,
            }
            for pair, count in sorted(failure_by_pair.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        recommendations = []
        for f in findings[:3]:
            if f["failure_count"] > 10:
                recommendations.append(
                    f"High failure rate from '{f['source']}' to '{f['destination']}' "
                    f"({f['failure_count']} failures) - check circuit breaker"
                )
        if not recommendations:
            recommendations.append("Failure rates are within normal range")

        result = AnalysisResult(
            AnalysisType.FAILURE_CHAIN,
            title="Failure Chain Analysis",
            findings=findings,
            recommendations=recommendations,
            details={"total_failures": len(chains)},
        )
        self._record_analysis(result)
        return result

    def analyze_resource_usage(self) -> AnalysisResult:
        """Analyze resource usage across services."""
        with self._lock:
            usage = dict(self._resource_usage)

        findings = [
            {
                "service": svc,
                "cpu": data.get("cpu", 0),
                "memory": data.get("memory", 0),
            }
            for svc, data in usage.items()
        ]
        findings.sort(key=lambda x: x["cpu"] + x["memory"], reverse=True)

        recommendations = []
        for f in findings[:5]:
            if f["cpu"] > 0.8:
                recommendations.append(
                    f"Service '{f['service']}' has high CPU usage ({f['cpu']:.1%}) - scale up"
                )
            if f["memory"] > 0.8:
                recommendations.append(
                    f"Service '{f['service']}' has high memory usage ({f['memory']:.1%}) - scale up"
                )
        if not recommendations:
            recommendations.append("Resource usage is within normal range")

        result = AnalysisResult(
            AnalysisType.RESOURCE_USAGE,
            title="Resource Usage Analysis",
            findings=findings,
            recommendations=recommendations,
            details={"service_count": len(usage)},
        )
        self._record_analysis(result)
        return result

    def analyze_all(self) -> List[AnalysisResult]:
        """Run all analyses."""
        return [
            self.analyze_traffic_pattern(),
            self.analyze_hot_services(),
            self.analyze_dependencies(),
            self.analyze_failure_chains(),
            self.analyze_resource_usage(),
        ]

    def _record_analysis(self, result: AnalysisResult) -> None:
        with self._lock:
            self._analysis_count += 1
            self._history.append(result)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    def get_history(self, limit: int = 100) -> List[AnalysisResult]:
        with self._lock:
            return list(self._history[-limit:])

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._started,
                "analysis_count": self._analysis_count,
                "history_count": len(self._history),
                "tracked_services": len(self._service_traffic),
                "dependency_edges": sum(len(v) for v in self._dependencies.values()),
            }

    def clear(self) -> None:
        with self._lock:
            self._service_traffic.clear()
            self._service_errors.clear()
            self._service_latency.clear()
            self._dependencies.clear()
            self._failure_chains.clear()
            self._resource_usage.clear()
            self._history.clear()
            self._analysis_count = 0
