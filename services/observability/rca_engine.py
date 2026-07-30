from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum


class RCACategory(Enum):
    NETWORK = "NETWORK"
    DATABASE = "DATABASE"
    EXTERNAL_DEPENDENCY = "EXTERNAL_DEPENDENCY"
    RESOURCE = "RESOURCE"
    CODE_DEFECT = "CODE_DEFECT"
    CONFIGURATION = "CONFIGURATION"
    THIRD_PARTY = "THIRD_PARTY"
    UNKNOWN = "UNKNOWN"


@dataclass
class IncidentContext:
    incident_id: str
    title: str
    description: str
    affected_service: str
    severity: str
    symptoms: List[str] = field(default_factory=list)
    affected_components: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RootCause:
    category: str
    description: str
    confidence: float
    evidence: List[str] = field(default_factory=list)
    related_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class RCAResult:
    incident_id: str
    root_cause: Optional[RootCause]
    contributing_factors: List[RootCause]
    impact_analysis: Dict[str, str]
    recommended_actions: List[str]
    confidence: float
    analyzed_at: datetime
    summary: str


class RCAEngine:
    def __init__(self):
        self._knowledge_base: Dict[str, List[Dict]] = {}
        self._analyses: List[RCAResult] = []

    def add_knowledge(
        self,
        category: str,
        patterns: List[str],
        causes: List[str],
        solutions: List[str],
    ):
        if category not in self._knowledge_base:
            self._knowledge_base[category] = []
        self._knowledge_base[category].append({
            "patterns": patterns,
            "causes": causes,
            "solutions": solutions,
        })

    def analyze(
        self,
        incident: IncidentContext,
        metrics: Optional[Dict[str, float]] = None,
        traces: Optional[List[Dict]] = None,
    ) -> RCAResult:
        metrics = metrics or {}
        traces = traces or []

        symptoms_text = " ".join(incident.symptoms).lower()
        evidence: List[str] = []
        root_cause: Optional[RootCause] = None
        contributing: List[RootCause] = []

        if "timeout" in symptoms_text or "latency" in symptoms_text:
            if metrics.get("queue_depth", 0) > 100:
                evidence.append(f"Queue depth high: {metrics.get('queue_depth')}")
                root_cause = RootCause(
                    category=RCACategory.RESOURCE.value,
                    description="Execution queue congestion causing timeouts",
                    confidence=0.85,
                    evidence=evidence,
                    related_metrics={"queue_depth": metrics.get("queue_depth", 0)},
                )
            elif metrics.get("db_latency_ms", 0) > 500:
                evidence.append(f"Database latency high: {metrics.get('db_latency_ms')}ms")
                root_cause = RootCause(
                    category=RCACategory.DATABASE.value,
                    description="Database query performance degradation",
                    confidence=0.82,
                    evidence=evidence,
                    related_metrics={"db_latency_ms": metrics.get("db_latency_ms", 0)},
                )
            else:
                evidence.append("Timeout without clear metric signal")
                root_cause = RootCause(
                    category=RCACategory.NETWORK.value,
                    description="Network latency or external service slowdown",
                    confidence=0.60,
                    evidence=evidence,
                )

        elif "memory" in symptoms_text or "oom" in symptoms_text:
            mem_pct = metrics.get("memory_used_pct", 0)
            evidence.append(f"Memory usage: {mem_pct}%")
            if mem_pct > 90:
                root_cause = RootCause(
                    category=RCACategory.RESOURCE.value,
                    description="Memory exhaustion - possible leak or under-provisioning",
                    confidence=0.90,
                    evidence=evidence,
                    related_metrics={"memory_used_pct": mem_pct},
                )
            else:
                root_cause = RootCause(
                    category=RCACategory.CODE_DEFECT.value,
                    description="Memory usage anomaly - potential memory leak",
                    confidence=0.55,
                    evidence=evidence,
                )

        elif "error rate" in symptoms_text or "failure" in symptoms_text:
            error_rate = metrics.get("error_rate", 0)
            evidence.append(f"Error rate: {error_rate}")
            if error_rate > 0.5:
                root_cause = RootCause(
                    category=RCACategory.CODE_DEFECT.value,
                    description="High error rate indicating code or configuration issue",
                    confidence=0.75,
                    evidence=evidence,
                    related_metrics={"error_rate": error_rate},
                )
            else:
                root_cause = RootCause(
                    category=RCACategory.EXTERNAL_DEPENDENCY.value,
                    description="Intermittent failures likely from upstream dependency",
                    confidence=0.50,
                    evidence=evidence,
                )

        elif "connectivity" in symptoms_text or "connection" in symptoms_text:
            evidence.append("Connectivity issues detected")
            root_cause = RootCause(
                category=RCACategory.NETWORK.value,
                description="Network connectivity issue",
                confidence=0.70,
                evidence=evidence,
            )

        if not root_cause:
            root_cause = RootCause(
                category=RCACategory.UNKNOWN.value,
                description="Unable to determine root cause from available data",
                confidence=0.10,
                evidence=["Insufficient diagnostic data"],
            )

        recommended = self._get_recommendations(root_cause.category)

        result = RCAResult(
            incident_id=incident.incident_id,
            root_cause=root_cause,
            contributing_factors=contributing,
            impact_analysis={
                "service": incident.affected_service,
                "severity": incident.severity,
                "components_affected": ", ".join(incident.affected_components) or "unknown",
            },
            recommended_actions=recommended,
            confidence=root_cause.confidence,
            analyzed_at=datetime.now(),
            summary=f"Root cause: {root_cause.description} (confidence: {root_cause.confidence:.0%})",
        )
        self._analyses.append(result)
        return result

    def _get_recommendations(self, category: str) -> List[str]:
        recommendations = {
            RCACategory.NETWORK.value: [
                "Check network connectivity between services",
                "Verify load balancer health",
                "Review DNS resolution and firewall rules",
            ],
            RCACategory.DATABASE.value: [
                "Review database query performance",
                "Check connection pool utilization",
                "Analyze slow query logs",
                "Consider adding read replicas or optimizing indexes",
            ],
            RCACategory.RESOURCE.value: [
                "Scale up affected service",
                "Review resource limits and quotas",
                "Check for resource leaks",
                "Implement auto-scaling policies",
            ],
            RCACategory.CODE_DEFECT.value: [
                "Review recent code changes",
                "Run automated tests on affected modules",
                "Check error logs for stack traces",
                "Consider rolling back recent deployments",
            ],
            RCACategory.CONFIGURATION.value: [
                "Verify recent configuration changes",
                "Check environment variables",
                "Review service mesh policies",
            ],
            RCACategory.EXTERNAL_DEPENDENCY.value: [
                "Check health of upstream services",
                "Review circuit breaker status",
                "Verify API rate limits",
                "Implement fallback mechanisms",
            ],
            RCACategory.THIRD_PARTY.value: [
                "Check third-party service status",
                "Review API credentials and quotas",
                "Contact vendor support",
            ],
        }
        return recommendations.get(category, [
            "Gather more diagnostic data",
            "Engage on-call engineer",
            "Review system logs and metrics",
        ])

    def get_analysis_history(self, limit: int = 20) -> List[RCAResult]:
        return sorted(self._analyses, key=lambda a: a.analyzed_at, reverse=True)[:limit]
