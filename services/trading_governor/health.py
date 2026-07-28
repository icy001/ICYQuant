"""System Health Monitor – real-time monitoring of all system components."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class HealthStatus(Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


@dataclass
class HealthReport:
    score: float
    status: HealthStatus
    components: Dict[str, float]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = field(default_factory=dict)


class SystemHealthMonitor:
    """Monitors system health across CPU, memory, Redis, Kafka, DB, Broker API, Exchange Feed."""

    CRITICAL_THRESHOLD = 60.0
    WARNING_THRESHOLD = 80.0

    # Default weights for each component
    DEFAULT_WEIGHTS = {
        "cpu": 0.10,
        "memory": 0.10,
        "redis": 0.15,
        "kafka": 0.15,
        "database": 0.15,
        "broker_api": 0.15,
        "exchange_feed": 0.20,
    }

    def evaluate(self, metrics: Dict[str, float]) -> float:
        """Return the minimum health score across all components.

        This is the simplest conservative approach — the system is only as
        healthy as its weakest component.

        Args:
            metrics: component_name → health_score (0-100) mapping.

        Returns:
            Minimum health score, or 100 if no metrics provided.
        """
        if not metrics:
            return 100.0
        return min(metrics.values())

    def weighted_evaluate(
        self,
        metrics: Dict[str, float],
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Weighted health score across components.

        Args:
            metrics: component_name → health_score (0-100).
            weights: component_name → weight (must sum reasonably).

        Returns:
            Weighted health score (0-100).
        """
        if not metrics:
            return 100.0

        weights = weights or self.DEFAULT_WEIGHTS
        total = 0.0
        total_weight = 0.0

        for name, score in metrics.items():
            w = weights.get(name, 0.0)
            total += score * w
            total_weight += w

        return total / total_weight if total_weight > 0 else 100.0

    def status(self, score: float) -> HealthStatus:
        """Map a health score to a status level."""
        if score >= self.WARNING_THRESHOLD:
            return HealthStatus.HEALTHY
        if score >= self.CRITICAL_THRESHOLD:
            return HealthStatus.DEGRADED
        return HealthStatus.UNHEALTHY

    def evaluate_full(
        self,
        metrics: Dict[str, float],
        weights: Optional[Dict[str, float]] = None,
    ) -> HealthReport:
        """Full health evaluation: score, status, component breakdown.

        Args:
            metrics: component_name → health_score.
            weights: optional per-component weights.

        Returns:
            HealthReport with score, status, and component details.
        """
        score = self.weighted_evaluate(metrics, weights)
        status = self.status(score)

        unhealthy = [k for k, v in metrics.items() if v < self.CRITICAL_THRESHOLD]
        degraded = [k for k, v in metrics.items() if self.CRITICAL_THRESHOLD <= v < self.WARNING_THRESHOLD]

        return HealthReport(
            score=round(score, 2),
            status=status,
            components=metrics,
            details={
                "unhealthy_components": unhealthy,
                "degraded_components": degraded,
                "healthy_components": [k for k in metrics if k not in unhealthy and k not in degraded],
            },
        )

    def is_trading_safe(self, score: float, min_threshold: float = 60.0) -> bool:
        """Check if system health is sufficient for trading."""
        return score >= min_threshold
