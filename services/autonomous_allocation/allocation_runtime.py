"""Allocation Runtime — live state tracking and event management.

Tracks current allocation state, processes runtime events,
and maintains the allocation loop's live operational state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class RuntimeEventType(str, Enum):
    """Types of runtime events in the allocation loop."""
    MARKET_DATA_UPDATE = "MARKET_DATA_UPDATE"
    STRATEGY_SIGNAL = "STRATEGY_SIGNAL"
    ALPHA_CHANGE = "ALPHA_CHANGE"
    RISK_CHANGE = "RISK_CHANGE"
    CAPACITY_CHANGE = "CAPACITY_CHANGE"
    LIQUIDITY_CHANGE = "LIQUIDITY_CHANGE"
    STRESS_CHANGE = "STRESS_CHANGE"
    SURVIVAL_CHANGE = "SURVIVAL_CHANGE"
    ALLOCATION_EXECUTED = "ALLOCATION_EXECUTED"
    REBALANCE_COMPLETE = "REBALANCE_COMPLETE"
    GUARD_TRIGGERED = "GUARD_TRIGGERED"
    MODE_CHANGE = "MODE_CHANGE"
    CAPITAL_INFLOW = "CAPITAL_INFLOW"
    CAPITAL_OUTFLOW = "CAPITAL_OUTFLOW"
    FEEDBACK_RECEIVED = "FEEDBACK_RECEIVED"
    ERROR_OCCURRED = "ERROR_OCCURRED"


class RuntimeState(str, Enum):
    """Runtime operational state."""
    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    RECALCULATING = "RECALCULATING"
    DECIDING = "DECIDING"
    EXECUTING = "EXECUTING"
    THROTTLED = "THROTTLED"
    FROZEN = "FROZEN"
    RECOVERING = "RECOVERING"
    STOPPED = "STOPPED"


@dataclass
class RuntimeEvent:
    """A runtime event in the allocation loop."""
    event_type: RuntimeEventType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    severity: str = "INFO"
    event_id: str = ""

    def __post_init__(self):
        if not self.event_id:
            ts = self.timestamp.strftime("%Y%m%d%H%M%S%f")
            self.event_id = f"evt-{ts}-{hash(str(self.data)) & 0xFFFF:04x}"


@dataclass
class AllocationRuntimeSnapshot:
    """Snapshot of runtime state at a point in time."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    state: RuntimeState = RuntimeState.IDLE
    total_capital: float = 0.0
    deployed_capital: float = 0.0
    reserve_ratio: float = 0.10
    buffer_ratio: float = 0.05
    active_strategies: int = 0
    pending_decisions: int = 0
    last_allocation_time: Optional[datetime] = None
    last_rebalance_time: Optional[datetime] = None
    uptime_seconds: float = 0.0
    event_count: int = 0
    error_count: int = 0


class AllocationRuntime:
    """Manages the live runtime state of the allocation system.

    Tracks events, maintains state machine, and provides
    snapshots for observability and decision-making.
    """

    def __init__(self, max_event_history: int = 10000):
        self._state = RuntimeState.IDLE
        self._events: List[RuntimeEvent] = []
        self._max_event_history = max_event_history
        self._start_time = datetime.utcnow()
        self._error_count = 0
        self._last_allocation: Optional[datetime] = None
        self._last_rebalance: Optional[datetime] = None
        self._handlers: Dict[RuntimeEventType, List[callable]] = {}
        self._frozen = False

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    @property
    def uptime_seconds(self) -> float:
        return (datetime.utcnow() - self._start_time).total_seconds()

    def register_handler(self, event_type: RuntimeEventType,
                         handler: callable) -> None:
        """Register an event handler."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def emit(self, event_type: RuntimeEventType, source: str = "",
             data: Optional[Dict[str, Any]] = None,
             severity: str = "INFO") -> RuntimeEvent:
        """Emit a runtime event and notify handlers."""
        if self._frozen and event_type not in (
            RuntimeEventType.GUARD_TRIGGERED,
            RuntimeEventType.ERROR_OCCURRED,
            RuntimeEventType.MODE_CHANGE,
        ):
            return RuntimeEvent(event_type=event_type, source=source,
                                data=data or {}, severity="BLOCKED")

        event = RuntimeEvent(
            event_type=event_type,
            source=source,
            data=data or {},
            severity=severity,
        )
        self._events.append(event)

        if len(self._events) > self._max_event_history:
            self._events = self._events[-self._max_event_history:]

        if event_type == RuntimeEventType.ERROR_OCCURRED:
            self._error_count += 1

        if event_type == RuntimeEventType.ALLOCATION_EXECUTED:
            self._last_allocation = event.timestamp

        if event_type == RuntimeEventType.REBALANCE_COMPLETE:
            self._last_rebalance = event.timestamp

        # Notify handlers
        for handler in self._handlers.get(event_type, []):
            try:
                handler(event)
            except Exception:
                pass

        return event

    def transition(self, new_state: RuntimeState) -> None:
        """Transition to a new runtime state."""
        valid_transitions = {
            RuntimeState.IDLE: {RuntimeState.IDLE, RuntimeState.ACTIVE, RuntimeState.STOPPED},
            RuntimeState.ACTIVE: {RuntimeState.ACTIVE, RuntimeState.RECALCULATING,
                                  RuntimeState.DECIDING, RuntimeState.EXECUTING,
                                  RuntimeState.THROTTLED, RuntimeState.FROZEN,
                                  RuntimeState.STOPPED},
            RuntimeState.RECALCULATING: {RuntimeState.ACTIVE, RuntimeState.DECIDING,
                                         RuntimeState.THROTTLED, RuntimeState.FROZEN,
                                         RuntimeState.STOPPED},
            RuntimeState.DECIDING: {RuntimeState.ACTIVE, RuntimeState.EXECUTING,
                                    RuntimeState.THROTTLED, RuntimeState.FROZEN,
                                    RuntimeState.STOPPED},
            RuntimeState.EXECUTING: {RuntimeState.ACTIVE, RuntimeState.DECIDING,
                                     RuntimeState.THROTTLED, RuntimeState.FROZEN,
                                     RuntimeState.STOPPED},
            RuntimeState.THROTTLED: {RuntimeState.ACTIVE, RuntimeState.FROZEN,
                                     RuntimeState.RECOVERING, RuntimeState.STOPPED},
            RuntimeState.FROZEN: {RuntimeState.RECOVERING, RuntimeState.STOPPED},
            RuntimeState.RECOVERING: {RuntimeState.ACTIVE, RuntimeState.THROTTLED,
                                      RuntimeState.STOPPED},
            RuntimeState.STOPPED: {RuntimeState.IDLE, RuntimeState.RECOVERING},
        }

        if new_state in valid_transitions.get(self._state, set()):
            old = self._state
            self._state = new_state
            self.emit(RuntimeEventType.MODE_CHANGE,
                      source="runtime",
                      data={"from": old.value, "to": new_state.value})
        else:
            raise ValueError(f"Invalid state transition: {self._state} → {new_state}")

    def freeze(self) -> None:
        """Freeze all allocation events."""
        self._frozen = True
        self.transition(RuntimeState.FROZEN)

    def unfreeze(self) -> None:
        """Unfreeze allocation events."""
        self._frozen = False
        self.transition(RuntimeState.RECOVERING)

    def snapshot(self) -> AllocationRuntimeSnapshot:
        """Take a snapshot of current runtime state."""
        return AllocationRuntimeSnapshot(
            timestamp=datetime.utcnow(),
            state=self._state,
            total_capital=0.0,
            deployed_capital=0.0,
            active_strategies=0,
            pending_decisions=0,
            last_allocation_time=self._last_allocation,
            last_rebalance_time=self._last_rebalance,
            uptime_seconds=self.uptime_seconds,
            event_count=len(self._events),
            error_count=self._error_count,
        )

    def recent_events(self, n: int = 100,
                      event_type: Optional[RuntimeEventType] = None) -> List[RuntimeEvent]:
        """Get recent events, optionally filtered by type."""
        events = self._events[-n:]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events

    def reset(self) -> None:
        """Reset runtime state."""
        self._state = RuntimeState.IDLE
        self._events.clear()
        self._error_count = 0
        self._frozen = False
        self._start_time = datetime.utcnow()
        self._last_allocation = None
        self._last_rebalance = None
