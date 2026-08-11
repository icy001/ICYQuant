"""
Capacity Memory — Records strategy capacity, utilization, and efficiency over time.

Tracks:
    - Capacity limits per strategy
    - Utilization trends
    - Marginal efficiency history
    - Capacity breach events
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class CapacityEventType(str, Enum):
    CAPACITY_SET = "capacity_set"
    CAPACITY_UPDATED = "capacity_updated"
    CAPACITY_APPROACHING = "capacity_approaching"   # >80% utilized
    CAPACITY_CRITICAL = "capacity_critical"          # >95% utilized
    CAPACITY_EXCEEDED = "capacity_exceeded"
    CAPACITY_RELEASED = "capacity_released"


@dataclass
class CapacityRecord:
    """A single capacity measurement point."""

    record_id: str = field(default_factory=lambda: f"CR-{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    strategy_id: str = ""
    capacity: float = 0.0              # Max capacity
    optimal_capital: float = 0.0       # Optimal capital for highest efficiency
    current_capital: float = 0.0       # Currently allocated

    utilization: float = 0.0           # current / capacity
    marginal_efficiency: float = 0.0   # Incremental return / incremental capital
    capital_efficiency: float = 0.0    # Return / capital

    event_type: CapacityEventType = CapacityEventType.CAPACITY_SET

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "strategy_id": self.strategy_id,
            "capacity": self.capacity,
            "optimal_capital": self.optimal_capital,
            "current_capital": self.current_capital,
            "utilization": self.utilization,
            "marginal_efficiency": self.marginal_efficiency,
            "capital_efficiency": self.capital_efficiency,
        }

    @property
    def remaining_capacity(self) -> float:
        return max(0.0, self.capacity - self.current_capital)

    @property
    def capacity_status(self) -> str:
        if self.utilization >= 1.0:
            return "EXCEEDED"
        elif self.utilization >= 0.95:
            return "CRITICAL"
        elif self.utilization >= 0.80:
            return "APPROACHING"
        elif self.utilization >= 0.50:
            return "MODERATE"
        return "LOW"


class CapacityMemory:
    """Tracks strategy capacity metrics over time."""

    def __init__(self, max_records_per_strategy: int = 5000):
        self._records: Dict[str, List[CapacityRecord]] = {}
        self._events: List[CapacityRecord] = []  # events (breaches, warnings)
        self._max_per_strategy = max_records_per_strategy

    def record(self, record: CapacityRecord) -> None:
        if record.strategy_id not in self._records:
            self._records[record.strategy_id] = []
        self._records[record.strategy_id].append(record)

        if len(self._records[record.strategy_id]) > self._max_per_strategy:
            self._records[record.strategy_id] = self._records[record.strategy_id][-self._max_per_strategy:]

        # Track threshold events
        if record.event_type in (
            CapacityEventType.CAPACITY_APPROACHING,
            CapacityEventType.CAPACITY_CRITICAL,
            CapacityEventType.CAPACITY_EXCEEDED,
        ):
            self._events.append(record)

    def latest(self, strategy_id: str) -> Optional[CapacityRecord]:
        records = self._records.get(strategy_id, [])
        return records[-1] if records else None

    def utilization_trend(self, strategy_id: str, n: int = 20) -> List[float]:
        records = self._records.get(strategy_id, [])
        return [r.utilization for r in records[-n:]]

    def efficiency_trend(self, strategy_id: str, n: int = 20) -> List[float]:
        records = self._records.get(strategy_id, [])
        return [r.marginal_efficiency for r in records[-n:]]

    def strategies_at_capacity(self, threshold: float = 0.80) -> List[str]:
        """Return strategies approaching or exceeding capacity."""
        result = []
        for sid in self._records:
            latest = self.latest(sid)
            if latest and latest.utilization >= threshold:
                result.append(sid)
        return result

    def highest_marginal_efficiency(self, top_n: int = 5) -> List[CapacityRecord]:
        """Return strategies with highest marginal capital efficiency."""
        all_latest = [self.latest(sid) for sid in self._records]
        valid = [r for r in all_latest if r is not None and r.marginal_efficiency > 0]
        valid.sort(key=lambda r: r.marginal_efficiency, reverse=True)
        return valid[:top_n]

    def recent_events(self, n: int = 50) -> List[CapacityRecord]:
        return self._events[-n:]

    def summary(self) -> Dict[str, Any]:
        strategies = list(self._records.keys())
        latest_records = [self.latest(sid) for sid in strategies if self.latest(sid)]
        if not latest_records:
            return {"strategy_count": 0}

        return {
            "strategy_count": len(strategies),
            "avg_utilization": sum(r.utilization for r in latest_records) / len(latest_records),
            "max_utilization": max(r.utilization for r in latest_records),
            "strategies_at_capacity": len(self.strategies_at_capacity(0.80)),
            "strategies_critical": len(self.strategies_at_capacity(0.95)),
            "recent_events": len(self._events),
        }
