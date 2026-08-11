"""
Strategy Capacity Monitor — Monitors capacity utilization and alerts on breaches.

Tracks utilization trends, capacity warnings, and degradation events.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class CapacityAlert(str, Enum):
    APPROACHING = "approaching"      # >70%
    NEAR_LIMIT = "near_limit"        # >85%
    AT_LIMIT = "at_limit"            # >95%
    EXCEEDED = "exceeded"            # >100%
    DEGRADED = "degraded"            # capacity reduced


@dataclass
class CapacityAlertEvent:
    """A capacity alert event."""

    event_id: str = field(default_factory=lambda: f"CA-{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    strategy_id: str = ""
    alert: CapacityAlert = CapacityAlert.APPROACHING
    utilization: float = 0.0
    current_capital: float = 0.0
    capacity_limit: float = float("inf")
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "strategy_id": self.strategy_id,
            "alert": self.alert.value,
            "utilization": self.utilization,
            "message": self.message,
        }


class StrategyCapacityMonitor:
    """Monitors capacity utilization across strategies."""

    def __init__(self, warning_threshold: float = 0.70, critical_threshold: float = 0.85):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self._utilization_history: Dict[str, List[Tuple[str, float]]] = {}
        self._alerts: List[CapacityAlertEvent] = []

    def record(self, strategy_id: str, current_capital: float, capacity_limit: float) -> Optional[CapacityAlertEvent]:
        utilization = current_capital / max(capacity_limit, 1.0) if capacity_limit < float("inf") else 0.0

        if strategy_id not in self._utilization_history:
            self._utilization_history[strategy_id] = []
        self._utilization_history[strategy_id].append(
            (datetime.now(timezone.utc).isoformat(), utilization)
        )

        # Alert logic
        if utilization >= 1.0:
            return self._create_alert(strategy_id, CapacityAlert.EXCEEDED, utilization, current_capital, capacity_limit)
        elif utilization >= 0.95:
            return self._create_alert(strategy_id, CapacityAlert.AT_LIMIT, utilization, current_capital, capacity_limit)
        elif utilization >= self.critical_threshold:
            return self._create_alert(strategy_id, CapacityAlert.NEAR_LIMIT, utilization, current_capital, capacity_limit)
        elif utilization >= self.warning_threshold:
            return self._create_alert(strategy_id, CapacityAlert.APPROACHING, utilization, current_capital, capacity_limit)
        return None

    def _create_alert(self, sid: str, alert: CapacityAlert, util: float,
                      capital: float, limit: float) -> CapacityAlertEvent:
        event = CapacityAlertEvent(
            strategy_id=sid, alert=alert, utilization=util,
            current_capital=capital, capacity_limit=limit,
            message=f"Strategy {sid}: {util:.1%} utilization — {alert.value}",
        )
        self._alerts.append(event)
        return event

    def recent_alerts(self, n: int = 50) -> List[CapacityAlertEvent]:
        return self._alerts[-n:]

    def utilization_trend(self, strategy_id: str, n: int = 20) -> List[float]:
        history = self._utilization_history.get(strategy_id, [])
        return [u for _, u in history[-n:]]

    def strategies_at_risk(self) -> List[str]:
        """Strategies with recent critical alerts."""
        return list(set(e.strategy_id for e in self._alerts[-20:] if e.alert in (CapacityAlert.NEAR_LIMIT, CapacityAlert.AT_LIMIT, CapacityAlert.EXCEEDED)))

    def summary(self) -> Dict[str, Any]:
        return {
            "monitored_strategies": len(self._utilization_history),
            "total_alerts": len(self._alerts),
            "strategies_at_risk": self.strategies_at_risk(),
        }
