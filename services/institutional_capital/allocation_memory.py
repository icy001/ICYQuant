"""
Allocation Memory — Records allocation decisions, weights, and changes over time.

Tracks:
    - Allocation history per strategy
    - Weight drift over time
    - Allocation change audit trail
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class AllocationChangeType(str, Enum):
    INITIAL = "initial"
    INCREASE = "increase"
    DECREASE = "decrease"
    REBALANCE = "rebalance"
    QUARANTINE = "quarantine"
    RELEASE = "release"
    FREEZE = "freeze"


@dataclass
class AllocationRecord:
    """A single allocation state record."""

    record_id: str = field(default_factory=lambda: f"AR-{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    strategy_id: str = ""
    account_id: str = ""

    capital: float = 0.0
    weight: float = 0.0
    risk_budget: float = 0.0

    expected_return: float = 0.0
    volatility: float = 0.0
    sharpe: float = 0.0
    capital_efficiency: float = 0.0

    change_type: AllocationChangeType = AllocationChangeType.INITIAL
    change_amount: float = 0.0
    reason: str = ""

    decision_id: str = ""
    trace_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "strategy_id": self.strategy_id,
            "capital": self.capital,
            "weight": self.weight,
            "risk_budget": self.risk_budget,
            "expected_return": self.expected_return,
            "sharpe": self.sharpe,
            "capital_efficiency": self.capital_efficiency,
            "change_type": self.change_type.value,
            "change_amount": self.change_amount,
        }


@dataclass
class AllocationSnapshot:
    """Full portfolio allocation snapshot at a point in time."""

    snapshot_id: str = field(default_factory=lambda: f"AS-{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_capital: float = 0.0
    allocations: Dict[str, AllocationRecord] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "total_capital": self.total_capital,
            "strategy_count": len(self.allocations),
            "allocations": {k: v.to_dict() for k, v in self.allocations.items()},
        }

    def weight_sum(self) -> float:
        return sum(a.weight for a in self.allocations.values())


class AllocationMemory:
    """Tracks allocation history and drift for all strategies."""

    def __init__(self, max_records_per_strategy: int = 5000):
        self._records: Dict[str, List[AllocationRecord]] = {}  # strategy_id -> records
        self._snapshots: List[AllocationSnapshot] = []
        self._max_per_strategy = max_records_per_strategy

    def record(self, record: AllocationRecord) -> None:
        if record.strategy_id not in self._records:
            self._records[record.strategy_id] = []
        self._records[record.strategy_id].append(record)
        if len(self._records[record.strategy_id]) > self._max_per_strategy:
            self._records[record.strategy_id] = self._records[record.strategy_id][-self._max_per_strategy:]

    def snapshot(self, snapshot: AllocationSnapshot) -> None:
        self._snapshots.append(snapshot)
        if len(self._snapshots) > 1000:
            self._snapshots = self._snapshots[-1000:]

    def strategy_history(self, strategy_id: str) -> List[AllocationRecord]:
        return self._records.get(strategy_id, [])

    def latest_allocation(self, strategy_id: str) -> Optional[AllocationRecord]:
        records = self._records.get(strategy_id, [])
        return records[-1] if records else None

    def current_weights(self) -> Dict[str, float]:
        weights: Dict[str, float] = {}
        for sid, records in self._records.items():
            if records:
                weights[sid] = records[-1].weight
        return weights

    def weight_drift(self, target_weights: Dict[str, float]) -> Dict[str, float]:
        """Calculate drift between current and target weights."""
        current = self.current_weights()
        drift: Dict[str, float] = {}
        all_ids = set(current.keys()) | set(target_weights.keys())
        for sid in all_ids:
            drift[sid] = target_weights.get(sid, 0.0) - current.get(sid, 0.0)
        return drift

    def latest_snapshot(self) -> Optional[AllocationSnapshot]:
        return self._snapshots[-1] if self._snapshots else None

    def total_records(self) -> int:
        return sum(len(r) for r in self._records.values())
