"""
Monitoring Adapter — Connects Strategy Platform to the Monitoring Platform.

Provides interface for emitting metrics, alerts, and health status
to the centralized monitoring infrastructure.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MonitorAlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class MonitorMetric:
    """A single monitoring metric."""
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metric_type: str = "gauge"  # gauge, counter, histogram


@dataclass
class MonitorAlert:
    """A monitoring alert."""
    alert_id: str
    name: str
    severity: MonitorAlertSeverity = MonitorAlertSeverity.WARNING
    message: str = ""
    source: str = "strategy_platform"
    strategy_id: Optional[str] = None
    tags: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False


class MonitoringAdapter:
    """
    Adapter for the centralized Monitoring Platform.

    Emits strategy-level metrics, alerts, and health signals
    to the monitoring infrastructure for dashboards and alerting.

    Usage::

        adapter = MonitoringAdapter()
        await adapter.initialize()
        await adapter.emit_metric(MonitorMetric(
            name="icyquant_strategy_signal_count",
            value=42.0,
            labels={"strategy_id": "strat_001"},
        ))
        await adapter.raise_alert(MonitorAlert(
            alert_id="alert_001",
            name="StrategyErrorRateHigh",
            severity=MonitorAlertSeverity.CRITICAL,
            message="Error rate exceeded 5% threshold",
        ))
    """

    def __init__(self) -> None:
        self._metrics: list[MonitorMetric] = []
        self._alerts: dict[str, MonitorAlert] = {}
        self._counter: int = 0
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the monitoring adapter."""
        self._initialized = True
        logger.info("MonitoringAdapter initialized.")

    async def stop(self) -> None:
        """Stop the adapter."""
        self._initialized = False
        logger.info("MonitoringAdapter stopped.")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def emit_metric(self, metric: MonitorMetric) -> None:
        """Emit a metric to the monitoring platform."""
        self._metrics.append(metric)
        logger.debug(f"Metric emitted: {metric.name}={metric.value}")

    async def emit_metrics(self, metrics: list[MonitorMetric]) -> None:
        """Emit multiple metrics at once."""
        self._metrics.extend(metrics)
        logger.debug(f"Metrics emitted: {len(metrics)} metrics")

    async def raise_alert(self, alert: MonitorAlert) -> MonitorAlert:
        """Raise an alert to the monitoring platform."""
        self._counter += 1
        if not alert.alert_id:
            alert.alert_id = f"alert_{self._counter:06d}"
        self._alerts[alert.alert_id] = alert
        logger.warning(f"Alert raised: [{alert.severity.value}] {alert.name}: {alert.message}")
        return alert

    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return False
        alert.acknowledged = True
        return True

    async def get_alert(self, alert_id: str) -> Optional[MonitorAlert]:
        """Get an alert by ID."""
        return self._alerts.get(alert_id)

    async def list_alerts(
        self,
        severity: Optional[MonitorAlertSeverity] = None,
        acknowledged: Optional[bool] = None,
        limit: int = 100,
    ) -> list[MonitorAlert]:
        """List alerts with optional filters."""
        results = list(self._alerts.values())
        if severity:
            results = [a for a in results if a.severity == severity]
        if acknowledged is not None:
            results = [a for a in results if a.acknowledged == acknowledged]
        return sorted(results, key=lambda a: a.timestamp, reverse=True)[:limit]

    async def get_unacknowledged_alerts(self) -> list[MonitorAlert]:
        """Get all unacknowledged alerts."""
        return [a for a in self._alerts.values() if not a.acknowledged]

    async def get_recent_metrics(
        self,
        name: Optional[str] = None,
        limit: int = 100,
    ) -> list[MonitorMetric]:
        """Get recent metrics, optionally filtered by name."""
        results = self._metrics
        if name:
            results = [m for m in results if m.name == name]
        return results[-limit:]

    async def health_check(self) -> dict[str, Any]:
        """Check adapter health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "metrics_emitted": len(self._metrics),
            "active_alerts": len([a for a in self._alerts.values() if not a.acknowledged]),
            "total_alerts": len(self._alerts),
        }
