"""
Capacity Memory — Append-only event log for capacity lifecycle events.

Provides audit trail for capacity changes, decisions, and state transitions.
Supports snapshotting for point-in-time recovery and analysis.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .capacity_intelligence import CapacitySnapshot


class CapacityEventType(str, Enum):
    """Types of capacity events."""
    STRATEGY_REGISTERED = "strategy_registered"
    CAPACITY_ASSESSED = "capacity_assessed"
    CAPACITY_UPDATED = "capacity_updated"
    CAPACITY_BREACH = "capacity_breach"
    CAPACITY_RESTORED = "capacity_restored"
    STATE_TRANSITION = "state_transition"
    FREEZE = "freeze"
    UNFREEZE = "unfreeze"
    DEGRADED = "degraded"
    RESTORED = "restored"
    DECISION_MADE = "decision_made"
    EXECUTION = "execution"
    SNAPSHOT = "snapshot"


@dataclass
class CapacityEvent:
    """A single capacity lifecycle event."""

    event_id: str = field(default_factory=lambda: f"CE-{uuid.uuid4().hex[:8]}")
    event_type: CapacityEventType = CapacityEventType.CAPACITY_ASSESSED
    strategy_id: str = ""
    asset: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Event data
    data: Dict[str, Any] = field(default_factory=dict)
    snapshot: Optional[CapacitySnapshot] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "strategy_id": self.strategy_id,
            "asset": self.asset,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


@dataclass
class CapacitySnapshotRecord:
    """A point-in-time snapshot of capacity state."""

    record_id: str = field(default_factory=lambda: f"CSR-{uuid.uuid4().hex[:8]}")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    label: str = ""

    # Capacity state
    strategy_capacities: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    asset_capacities: Dict[str, float] = field(default_factory=dict)
    market_liquidity: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    utilization: Dict[str, float] = field(default_factory=dict)

    # Aggregates
    total_deployed: float = 0.0
    total_capacity: float = float("inf")
    overall_utilization: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp.isoformat(),
            "label": self.label,
            "total_deployed": self.total_deployed,
            "total_capacity": self.total_capacity,
            "overall_utilization": self.overall_utilization,
            "strategy_count": len(self.strategy_capacities),
            "asset_count": len(self.asset_capacities),
        }


class CapacityMemory:
    """Append-only event log for capacity lifecycle.

    Supports: event recording, snapshotting, replay, and querying.
    """

    def __init__(self):
        self._events: List[CapacityEvent] = []
        self._snapshots: List[CapacitySnapshotRecord] = []
        self._capacity_store: Dict[str, Dict[str, Any]] = {}
        self._max_events: int = 10000
        self._max_snapshots: int = 100

    # ── Event Recording ───────────────────────────────────────────

    def record_event(self,
                     event_type: CapacityEventType,
                     strategy_id: str = "",
                     asset: str = "",
                     data: Optional[Dict[str, Any]] = None,
                     snapshot: Optional[CapacitySnapshot] = None) -> CapacityEvent:
        """Record a capacity event."""
        event = CapacityEvent(
            event_type=event_type,
            strategy_id=strategy_id,
            asset=asset,
            data=data or {},
            snapshot=snapshot,
        )

        self._events.append(event)

        # Update capacity store
        key = f"{strategy_id}:{asset}" if strategy_id else asset
        if data:
            self._capacity_store.setdefault(key, {}).update(data)

        # Prune old events
        while len(self._events) > self._max_events:
            self._events.pop(0)

        return event

    # ── Snapshot ──────────────────────────────────────────────────

    def create_snapshot(self,
                        label: str = "",
                        strategy_capacities: Optional[Dict[str, Dict[str, Any]]] = None,
                        asset_capacities: Optional[Dict[str, float]] = None,
                        utilization: Optional[Dict[str, float]] = None,
                        total_deployed: float = 0.0,
                        total_capacity: float = float("inf")) -> CapacitySnapshotRecord:
        """Create a point-in-time snapshot of capacity state."""
        record = CapacitySnapshotRecord(
            label=label,
            strategy_capacities=strategy_capacities or {},
            asset_capacities=asset_capacities or {},
            utilization=utilization or {},
            total_deployed=total_deployed,
            total_capacity=total_capacity,
            overall_utilization=total_deployed / total_capacity if total_capacity > 0 else 0.0,
        )
        self._snapshots.append(record)

        # Record event
        self.record_event(
            event_type=CapacityEventType.SNAPSHOT,
            data={"label": label, "record_id": record.record_id},
        )

        # Prune
        while len(self._snapshots) > self._max_snapshots:
            self._snapshots.pop(0)

        return record

    # ── Queries ───────────────────────────────────────────────────

    def recent_events(self, limit: int = 100) -> List[CapacityEvent]:
        return self._events[-limit:]

    def events_by_type(self, event_type: CapacityEventType) -> List[CapacityEvent]:
        return [e for e in self._events if e.event_type == event_type]

    def events_by_strategy(self, strategy_id: str) -> List[CapacityEvent]:
        return [e for e in self._events if e.strategy_id == strategy_id]

    def events_by_asset(self, asset: str) -> List[CapacityEvent]:
        return [e for e in self._events if e.asset == asset]

    def events_since(self, since: datetime) -> List[CapacityEvent]:
        return [e for e in self._events if e.timestamp >= since]

    def events_between(self, start: datetime, end: datetime) -> List[CapacityEvent]:
        return [e for e in self._events if start <= e.timestamp <= end]

    def latest_snapshot(self) -> Optional[CapacitySnapshotRecord]:
        return self._snapshots[-1] if self._snapshots else None

    def snapshots_since(self, since: datetime) -> List[CapacitySnapshotRecord]:
        return [s for s in self._snapshots if s.timestamp >= since]

    def get_capacity(self, key: str) -> Optional[Dict[str, Any]]:
        return self._capacity_store.get(key)

    def capacity_breaches(self) -> List[CapacityEvent]:
        return self.events_by_type(CapacityEventType.CAPACITY_BREACH)

    def freeze_events(self) -> List[CapacityEvent]:
        return self.events_by_type(CapacityEventType.FREEZE)

    # ── Event counts ──────────────────────────────────────────────

    def event_count(self) -> int:
        return len(self._events)

    def snapshot_count(self) -> int:
        return len(self._snapshots)

    # ── Utility ───────────────────────────────────────────────────

    def clear(self) -> None:
        self._events.clear()
        self._snapshots.clear()
        self._capacity_store.clear()

    def set_max_events(self, max_events: int) -> None:
        self._max_events = max_events

    def set_max_snapshots(self, max_snapshots: int) -> None:
        self._max_snapshots = max_snapshots

    def summary(self) -> Dict[str, Any]:
        return {
            "total_events": self.event_count(),
            "total_snapshots": self.snapshot_count(),
            "event_types": {
                et.value: len(self.events_by_type(et))
                for et in CapacityEventType
                if self.events_by_type(et)
            },
            "latest_snapshot": self.latest_snapshot().to_dict() if self._snapshots else None,
            "breaches": len(self.capacity_breaches()),
            "freezes": len(self.freeze_events()),
        }
