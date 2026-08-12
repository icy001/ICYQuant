"""
ComponentRegistry — registration, heartbeat and health-score bookkeeping.

The Control Plane maintains a registry of every known component:

    component_id       e.g. "position_service"
    component_type     e.g. ComponentType.POSITION_SERVICE
    criticality        TRADING_CRITICAL / OPERATIONAL / NON_CRITICAL
    version            running version
    state              current ComponentState
    health_score       0..100 (auxiliary metric — never decides trading by itself)
    last_heartbeat_at  last time the component reported a HEARTBEAT
    last_state_change  last time the state changed
    registered_at      registration timestamp
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .component_state import ComponentState


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ComponentType(str, Enum):
    """Well-known component types tracked by the Control Plane."""

    EVENT_BUS = "event_bus"
    ORDER_ENGINE = "order_engine"
    RISK_ENGINE = "risk_engine"
    EXECUTION_ENGINE = "execution_engine"
    POSITION_SERVICE = "position_service"
    LEDGER_SERVICE = "ledger_service"
    STRATEGY_ENGINE = "strategy_engine"
    RECONCILIATION_ENGINE = "reconciliation_engine"
    RECOVERY_ENGINE = "recovery_engine"
    ANALYTICS = "analytics"
    REPORTING = "reporting"
    RESEARCH = "research"
    DASHBOARD = "dashboard"


class ComponentCriticality(str, Enum):
    """How a component failure affects the trading core path."""

    TRADING_CRITICAL = "TRADING_CRITICAL"
    """Unavailability must halt trading (Event Bus / Risk / Execution)."""

    OPERATIONAL = "OPERATIONAL"
    """Unavailability degrades trading (Position / Ledger / Order / Strategy ...)."""

    NON_CRITICAL = "NON_CRITICAL"
    """Unavailability has no impact on trading (Analytics / Reporting / ...)."""


# Canonical component ids (== ComponentType.value) that the Trading Gate watches.
TRADING_CRITICAL_IDS: Tuple[str, ...] = (
    ComponentType.EVENT_BUS.value,
    ComponentType.RISK_ENGINE.value,
    ComponentType.EXECUTION_ENGINE.value,
)


def default_criticality(component_type: ComponentType) -> ComponentCriticality:
    """Default criticality for a well-known component type."""
    if component_type in {
        ComponentType.EVENT_BUS,
        ComponentType.RISK_ENGINE,
        ComponentType.EXECUTION_ENGINE,
    }:
        return ComponentCriticality.TRADING_CRITICAL
    if component_type in {
        ComponentType.ORDER_ENGINE,
        ComponentType.POSITION_SERVICE,
        ComponentType.LEDGER_SERVICE,
        ComponentType.STRATEGY_ENGINE,
        ComponentType.RECONCILIATION_ENGINE,
        ComponentType.RECOVERY_ENGINE,
    }:
        return ComponentCriticality.OPERATIONAL
    return ComponentCriticality.NON_CRITICAL


@dataclass
class ComponentInfo:
    """One registered component and its live bookkeeping."""

    component_id: str
    component_type: ComponentType
    version: str
    state: ComponentState = ComponentState.STARTING
    criticality: Optional[ComponentCriticality] = None
    health_score: float = 100.0
    last_heartbeat_at: Optional[datetime] = None
    last_state_change: Optional[datetime] = None
    registered_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.criticality is None:
            self.criticality = default_criticality(self.component_type)
        now = _utcnow()
        if self.registered_at is None:
            self.registered_at = now
        if self.last_state_change is None:
            self.last_state_change = now

    # -- mutation ---------------------------------------------------------

    def mark_heartbeat(self, at: Optional[datetime] = None) -> None:
        """Record a HEARTBEAT at ``at`` (defaults to now)."""
        self.last_heartbeat_at = at or _utcnow()

    def update_state(self, new_state: ComponentState, at: Optional[datetime] = None) -> bool:
        """Apply a state change; returns True when the state actually changed."""
        if self.state == new_state:
            return False
        self.state = new_state
        self.last_state_change = at or _utcnow()
        return True

    def set_health_score(self, score: float) -> None:
        """Set the auxiliary health score, clamped to 0..100."""
        self.health_score = max(0.0, min(100.0, float(score)))

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_type": self.component_type.value,
            "version": self.version,
            "state": self.state.value,
            "criticality": self.criticality.value,
            "health_score": self.health_score,
            "last_heartbeat_at": self.last_heartbeat_at.isoformat()
            if self.last_heartbeat_at is not None
            else None,
            "last_state_change": self.last_state_change.isoformat()
            if self.last_state_change is not None
            else None,
            "registered_at": self.registered_at.isoformat()
            if self.registered_at is not None
            else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComponentInfo":
        return cls(
            component_id=data["component_id"],
            component_type=ComponentType(data["component_type"]),
            version=data["version"],
            state=ComponentState(data["state"]),
            criticality=ComponentCriticality(data["criticality"]),
            health_score=float(data.get("health_score", 100.0)),
            last_heartbeat_at=datetime.fromisoformat(data["last_heartbeat_at"])
            if data.get("last_heartbeat_at")
            else None,
            last_state_change=datetime.fromisoformat(data["last_state_change"])
            if data.get("last_state_change")
            else None,
            registered_at=datetime.fromisoformat(data["registered_at"])
            if data.get("registered_at")
            else None,
        )


@dataclass
class ComponentRegistry:
    """In-memory registry keyed by ``component_id``."""

    _components: Dict[str, ComponentInfo] = field(default_factory=dict)

    # -- queries ----------------------------------------------------------

    def get(self, component_id: str) -> Optional[ComponentInfo]:
        return self._components.get(component_id)

    def has(self, component_id: str) -> bool:
        return component_id in self._components

    def list_components(self) -> List[ComponentInfo]:
        return list(self._components.values())

    def component_count(self) -> int:
        return len(self._components)

    def states(self) -> Dict[str, ComponentState]:
        """Map of component_id -> current ComponentState."""
        return {cid: info.state for cid, info in self._components.items()}

    def critical_components(self) -> List[ComponentInfo]:
        return [i for i in self._components.values() if i.criticality is ComponentCriticality.TRADING_CRITICAL]

    # -- mutation ---------------------------------------------------------

    def register(
        self,
        component_id: str,
        component_type: ComponentType,
        version: str,
        state: ComponentState = ComponentState.STARTING,
        criticality: Optional[ComponentCriticality] = None,
        now: Optional[datetime] = None,
    ) -> ComponentInfo:
        """Register a component (idempotent — re-registration returns existing)."""
        existing = self._components.get(component_id)
        if existing is not None:
            return existing
        info = ComponentInfo(
            component_id=component_id,
            component_type=component_type,
            version=version,
            state=state,
            criticality=criticality,
        )
        if now is not None:
            info.registered_at = now
            info.last_state_change = now
        self._components[component_id] = info
        return info

    def update_state(
        self,
        component_id: str,
        new_state: ComponentState,
        at: Optional[datetime] = None,
    ) -> Optional[Tuple[ComponentState, bool]]:
        """Apply a state change; returns (previous_state, changed) or None if unknown."""
        info = self._components.get(component_id)
        if info is None:
            return None
        previous = info.state
        changed = info.update_state(new_state, at)
        return previous, changed

    def heartbeat(self, component_id: str, at: Optional[datetime] = None) -> Optional[ComponentInfo]:
        info = self._components.get(component_id)
        if info is None:
            return None
        info.mark_heartbeat(at)
        return info

    def apply_heartbeat_timeout(
        self,
        now: datetime,
        timeout_ms: int,
    ) -> List[Tuple[str, ComponentState]]:
        """
        Mark components whose last heartbeat is older than ``timeout_ms`` as UNKNOWN.

        Returns [(component_id, previous_state), ...] for every component that
        just transitioned to UNKNOWN.  Components that never heartbeated
        (last_heartbeat_at is None) are skipped.
        """
        timed_out: List[Tuple[str, ComponentState]] = []
        for info in self._components.values():
            if info.state is ComponentState.UNKNOWN:
                continue
            if info.last_heartbeat_at is None:
                continue
            age_ms = (now - info.last_heartbeat_at).total_seconds() * 1000.0
            if age_ms > timeout_ms:
                previous = info.state
                if info.update_state(ComponentState.UNKNOWN, now):
                    timed_out.append((info.component_id, previous))
        return timed_out


DEFAULT_COMPONENT_TYPES: Tuple[ComponentType, ...] = (
    ComponentType.EVENT_BUS,
    ComponentType.ORDER_ENGINE,
    ComponentType.RISK_ENGINE,
    ComponentType.EXECUTION_ENGINE,
    ComponentType.POSITION_SERVICE,
    ComponentType.LEDGER_SERVICE,
    ComponentType.STRATEGY_ENGINE,
    ComponentType.RECONCILIATION_ENGINE,
    ComponentType.RECOVERY_ENGINE,
)


def register_default_components(
    version: str = "1.0.0",
    now: Optional[datetime] = None,
) -> ComponentRegistry:
    """Create a registry pre-populated with the standard component set."""
    registry = ComponentRegistry()
    for component_type in DEFAULT_COMPONENT_TYPES:
        registry.register(
            component_id=component_type.value,
            component_type=component_type,
            version=version,
            now=now,
        )
    return registry
