"""
Capital Memory — Persistent record of capital pool states, decisions, and lifecycle events.

Provides audit trail for capital movements: allocation, reservation, deployment, release.
"""

from __future__ import annotations

import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class CapitalEventType(str, Enum):
    POOL_CREATED = "pool_created"
    POOL_UPDATED = "pool_updated"
    CAPITAL_ALLOCATED = "capital_allocated"
    CAPITAL_RESERVED = "capital_reserved"
    CAPITAL_RELEASED = "capital_released"
    CAPITAL_DEPLOYED = "capital_deployed"
    CAPITAL_RECONCILED = "capital_reconciled"
    ACCOUNT_CREATED = "account_created"
    ACCOUNT_UPDATED = "account_updated"
    BUDGET_SET = "budget_set"
    BUDGET_EXCEEDED = "budget_exceeded"


@dataclass
class CapitalEvent:
    """A single capital-related event for the audit trail."""

    event_id: str = field(default_factory=lambda: f"CE-{uuid.uuid4().hex[:8]}")
    event_type: CapitalEventType = CapitalEventType.POOL_UPDATED
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    pool_id: str = ""
    account_id: str = ""
    strategy_id: str = ""

    before_amount: float = 0.0
    after_amount: float = 0.0
    delta: float = 0.0

    reason: str = ""
    decision_id: str = ""
    trace_id: str = ""

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.event_type.value,
            "timestamp": self.timestamp,
            "pool_id": self.pool_id,
            "account_id": self.account_id,
            "strategy_id": self.strategy_id,
            "before_amount": self.before_amount,
            "after_amount": self.after_amount,
            "delta": self.delta,
            "reason": self.reason,
            "decision_id": self.decision_id,
        }


@dataclass
class CapitalSnapshot:
    """A point-in-time snapshot of capital pool state."""

    snapshot_id: str = field(default_factory=lambda: f"CS-{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    pool_id: str = ""
    total_capital: float = 0.0
    available_capital: float = 0.0
    reserved_capital: float = 0.0
    allocated_capital: float = 0.0
    deployed_capital: float = 0.0

    account_balances: Dict[str, float] = field(default_factory=dict)
    strategy_allocations: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "total_capital": self.total_capital,
            "available_capital": self.available_capital,
            "reserved_capital": self.reserved_capital,
            "allocated_capital": self.allocated_capital,
            "deployed_capital": self.deployed_capital,
            "account_count": len(self.account_balances),
            "strategy_count": len(self.strategy_allocations),
        }


class CapitalMemory:
    """Append-only memory store for capital events and snapshots."""

    def __init__(self, max_events: int = 10000, max_snapshots: int = 1000):
        self._events: List[CapitalEvent] = []
        self._snapshots: List[CapitalSnapshot] = []
        self._max_events = max_events
        self._max_snapshots = max_snapshots

    def record_event(self, event: CapitalEvent) -> None:
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

    def record_snapshot(self, snapshot: CapitalSnapshot) -> None:
        self._snapshots.append(snapshot)
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]

    def recent_events(self, n: int = 100) -> List[CapitalEvent]:
        return self._events[-n:]

    def events_by_type(self, event_type: CapitalEventType) -> List[CapitalEvent]:
        return [e for e in self._events if e.event_type == event_type]

    def events_by_strategy(self, strategy_id: str) -> List[CapitalEvent]:
        return [e for e in self._events if e.strategy_id == strategy_id]

    def events_by_account(self, account_id: str) -> List[CapitalEvent]:
        return [e for e in self._events if e.account_id == account_id]

    def latest_snapshot(self) -> Optional[CapitalSnapshot]:
        return self._snapshots[-1] if self._snapshots else None

    def snapshots_since(self, iso_timestamp: str) -> List[CapitalSnapshot]:
        return [s for s in self._snapshots if s.timestamp >= iso_timestamp]

    def capital_timeline(self, field: str = "total_capital") -> List[Dict[str, Any]]:
        """Get time series of a specific capital field."""
        return [
            {"timestamp": s.timestamp, field: getattr(s, field, 0.0)}
            for s in self._snapshots
        ]

    def total_events(self) -> int:
        return len(self._events)

    def total_snapshots(self) -> int:
        return len(self._snapshots)

    def clear(self) -> None:
        self._events.clear()
        self._snapshots.clear()
