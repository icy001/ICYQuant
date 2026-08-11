"""
Strategy Observability — Unified observability for the Strategy Platform.

Aggregates latency, signal counts, order intents, runtime metrics,
errors, and recovery events into a comprehensive observability report.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ObservabilityLevel(str, Enum):
    """Observability detail level."""
    BASIC = "basic"
    DETAILED = "detailed"
    FULL = "full"


@dataclass
class ObservabilityReport:
    """Comprehensive observability report."""
    platform_id: str = "strategy_platform"
    level: ObservabilityLevel = ObservabilityLevel.DETAILED
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Platform metrics
    strategies_total: int = 0
    strategies_running: int = 0
    strategies_paused: int = 0
    strategies_failed: int = 0

    # Performance
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    signal_count_total: int = 0
    signal_rate_per_second: float = 0.0

    # Order intent
    order_intent_total: int = 0
    order_intent_accepted: int = 0
    order_intent_rejected: int = 0

    # Events
    events_total: int = 0
    events_per_second: float = 0.0

    # Errors
    errors_total: int = 0
    error_rate_pct: float = 0.0
    recovery_events: int = 0

    # Health
    health_status: str = "healthy"
    uptime_seconds: float = 0.0

    # Details (full level only)
    details: dict[str, Any] = field(default_factory=dict)


class StrategyObservability:
    """
    Unified observability for the Strategy Platform.

    Aggregates metrics from all platform subsystems into
    comprehensive observability reports for dashboards and alerting.

    Usage::

        obs = StrategyObservability()
        await obs.initialize()
        report = await obs.generate_report(ObservabilityLevel.DETAILED)
    """

    def __init__(self) -> None:
        self._metrics: dict[str, list[tuple[datetime, float]]] = {}
        self._reports: list[ObservabilityReport] = []
        self._started_at: Optional[datetime] = None
        self._error_count: int = 0
        self._recovery_count: int = 0
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the observability system."""
        self._started_at = datetime.now(timezone.utc)
        self._initialized = True
        logger.info("StrategyObservability initialized.")

    async def stop(self) -> None:
        """Stop the observability system."""
        self._initialized = False
        logger.info("StrategyObservability stopped.")

    # ---- Metric Recording ----

    async def record_metric(self, name: str, value: float) -> None:
        """Record a metric observation."""
        if name not in self._metrics:
            self._metrics[name] = []
        self._metrics[name].append((datetime.now(timezone.utc), value))
        # Keep last 1000 observations per metric
        if len(self._metrics[name]) > 1000:
            self._metrics[name] = self._metrics[name][-1000:]

    async def record_latency(self, operation: str, latency_ms: float) -> None:
        """Record a latency observation."""
        await self.record_metric(f"latency.{operation}", latency_ms)

    async def record_error(self) -> None:
        """Record an error event."""
        self._error_count += 1

    async def record_recovery(self) -> None:
        """Record a recovery event."""
        self._recovery_count += 1

    # ---- Reporting ----

    async def generate_report(
        self,
        level: ObservabilityLevel = ObservabilityLevel.DETAILED,
    ) -> ObservabilityReport:
        """Generate an observability report."""
        report = ObservabilityReport(
            level=level,
            errors_total=self._error_count,
            recovery_events=self._recovery_count,
        )

        if self._started_at:
            report.uptime_seconds = (datetime.now(timezone.utc) - self._started_at).total_seconds()

        # Calculate error rate
        if report.events_total > 0:
            report.error_rate_pct = (self._error_count / report.events_total) * 100

        self._reports.append(report)
        if len(self._reports) > 100:
            self._reports = self._reports[-100:]

        return report

    async def get_latest_report(self) -> Optional[ObservabilityReport]:
        """Get the most recent observability report."""
        return self._reports[-1] if self._reports else None

    async def get_metric_summary(self, name: str) -> Optional[dict[str, Any]]:
        """Get summary statistics for a metric."""
        observations = self._metrics.get(name, [])
        if not observations:
            return None
        values = [v for _, v in observations]
        values.sort()
        n = len(values)
        return {
            "name": name,
            "count": n,
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / n,
            "p50": values[int(n * 0.5)],
            "p99": values[int(n * 0.99)] if n > 1 else values[-1],
        }

    async def health_check(self) -> dict[str, Any]:
        """Check observability health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "metrics_tracked": len(self._metrics),
            "errors_total": self._error_count,
            "recoveries": self._recovery_count,
            "uptime_seconds": (datetime.now(timezone.utc) - self._started_at).total_seconds() if self._started_at else 0,
        }
