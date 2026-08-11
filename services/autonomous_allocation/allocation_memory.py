"""Allocation Memory — persistent record of allocation decisions.

Append-only event log with snapshots for audit trail and
historical analysis of allocation decisions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class MemoryEventType(str, Enum):
    """Types of memory events."""
    ALLOCATION_REQUESTED = "ALLOCATION_REQUESTED"
    ALLOCATION_APPROVED = "ALLOCATION_APPROVED"
    ALLOCATION_REJECTED = "ALLOCATION_REJECTED"
    ALLOCATION_EXECUTED = "ALLOCATION_EXECUTED"
    ALLOCATION_COMPLETED = "ALLOCATION_COMPLETED"
    REBALANCE_TRIGGERED = "REBALANCE_TRIGGERED"
    REBALANCE_COMPLETED = "REBALANCE_COMPLETED"
    GUARD_ACTION = "GUARD_ACTION"
    ROTATION_EXECUTED = "ROTATION_EXECUTED"
    STATE_SNAPSHOT = "STATE_SNAPSHOT"
    ERROR = "ERROR"


@dataclass
class MemoryEvent:
    """A single event in the allocation memory log."""
    event_type: MemoryEventType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    strategy_id: str = ""
    decision_id: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    event_id: str = ""

    def __post_init__(self):
        if not self.event_id:
            ts = self.timestamp.strftime("%Y%m%d%H%M%S%f")
            self.event_id = f"mem-{ts}-{hash(str(self.data)) & 0xFFFF:04x}"


@dataclass
class AllocationSnapshot:
    """Snapshot of allocation state at a point in time."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_capital: float = 0.0
    allocations: Dict[str, float] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)
    scores: Dict[str, Dict[str, float]] = field(default_factory=dict)
    reserve: float = 0.0
    buffer: float = 0.0
    snapshot_id: str = ""

    def __post_init__(self):
        if not self.snapshot_id:
            ts = self.timestamp.strftime("%Y%m%d%H%M%S%f")
            self.snapshot_id = f"snap-{ts}"


class AllocationMemory:
    """Append-only event log with periodic snapshots.

    Provides: audit trail, historical reconstruction,
    and drift analysis for allocation decisions.
    """

    def __init__(self, max_events: int = 50000, max_snapshots: int = 1000):
        self._events: List[MemoryEvent] = []
        self._snapshots: List[AllocationSnapshot] = []
        self._max_events = max_events
        self._max_snapshots = max_snapshots

    def record(self, event_type: MemoryEventType, strategy_id: str = "",
               decision_id: str = "", data: Optional[Dict[str, Any]] = None) -> MemoryEvent:
        """Record an allocation memory event."""
        event = MemoryEvent(
            event_type=event_type,
            strategy_id=strategy_id,
            decision_id=decision_id,
            data=data or {},
        )
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]
        return event

    def snapshot(self, total_capital: float,
                 allocations: Dict[str, float],
                 weights: Dict[str, float],
                 scores: Dict[str, Dict[str, float]],
                 reserve: float = 0.0, buffer: float = 0.0) -> AllocationSnapshot:
        """Create a state snapshot."""
        snap = AllocationSnapshot(
            total_capital=total_capital,
            allocations=dict(allocations),
            weights=dict(weights),
            scores={k: dict(v) for k, v in scores.items()},
            reserve=reserve,
            buffer=buffer,
        )
        self._snapshots.append(snap)
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]

        # Also record as event
        self.record(
            event_type=MemoryEventType.STATE_SNAPSHOT,
            data={"snapshot_id": snap.snapshot_id},
        )
        return snap

    def get_events(self, event_type: Optional[MemoryEventType] = None,
                   strategy_id: Optional[str] = None,
                   limit: int = 100) -> List[MemoryEvent]:
        """Query events with optional filters."""
        events = self._events
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if strategy_id:
            events = [e for e in events if e.strategy_id == strategy_id]
        return events[-limit:]

    def get_latest_snapshot(self) -> Optional[AllocationSnapshot]:
        """Get the most recent snapshot."""
        return self._snapshots[-1] if self._snapshots else None

    def get_snapshots(self, limit: int = 10) -> List[AllocationSnapshot]:
        """Get recent snapshots."""
        return self._snapshots[-limit:]

    def compute_weight_drift(self,
                              current_weights: Dict[str, float]) -> Dict[str, float]:
        """Compute drift from last snapshot weights."""
        latest = self.get_latest_snapshot()
        if not latest:
            return {}

        drift = {}
        for sid, weight in current_weights.items():
            prev_weight = latest.weights.get(sid, 0.0)
            drift[sid] = weight - prev_weight
        return drift

    def clear(self) -> None:
        """Clear all memory."""
        self._events.clear()
        self._snapshots.clear()

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)
