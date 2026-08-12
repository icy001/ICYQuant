"""
ControlPlaneRepository — persistence for the Control Plane.

Stores three kinds of data:

    1. Component records          — current bookkeeping per component
    2. Control-plane event log    — the SOURCE OF TRUTH (event-sourced)
    3. ControlPlaneSnapshot       — the current operational VIEW (projection)

The snapshot is a projection and can always be rebuilt by replaying the event
log (``replay_events`` + ``ControlPlaneService.rebuild_snapshot``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..domain.component_registry import ComponentInfo, ComponentRegistry
from ..domain.component_state import ComponentState
from ..domain.control_plane_snapshot import ControlPlaneSnapshot
from ..domain.system_state import SystemState
from ..domain.trading_state import TradingState


@dataclass
class ControlPlaneRepository:
    """In-memory repository for the Control Plane."""

    _components: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _events: List[Dict[str, Any]] = field(default_factory=list)
    _snapshot: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # components
    # ------------------------------------------------------------------

    def save_component(self, info: ComponentInfo) -> None:
        self._components[info.component_id] = info.to_dict()

    def get_component(self, component_id: str) -> Optional[ComponentInfo]:
        data = self._components.get(component_id)
        return ComponentInfo.from_dict(data) if data is not None else None

    def list_components(self) -> List[ComponentInfo]:
        return [ComponentInfo.from_dict(d) for d in self._components.values()]

    def component_count(self) -> int:
        return len(self._components)

    def clear_components(self) -> None:
        self._components.clear()

    # ------------------------------------------------------------------
    # event log (source of truth)
    # ------------------------------------------------------------------

    def append_event(self, event: Any) -> str:
        """Persist an event; assigns a monotonic event_id when missing."""
        payload = event.to_dict() if hasattr(event, "to_dict") else dict(event)
        if not payload.get("event_id"):
            payload["event_id"] = f"CP-{len(self._events) + 1:05d}"
        self._events.append(payload)
        return payload["event_id"]

    def get_events(self, offset: int = 0, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        events = self._events[offset:]
        if limit is not None:
            events = events[:limit]
        return events

    def event_count(self) -> int:
        return len(self._events)

    # ------------------------------------------------------------------
    # snapshot (projection — rebuildable from the event log)
    # ------------------------------------------------------------------

    def save_snapshot(self, snapshot: ControlPlaneSnapshot) -> None:
        self._snapshot = snapshot.to_dict()

    def get_snapshot(self) -> Optional[ControlPlaneSnapshot]:
        if self._snapshot is None:
            return None
        return ControlPlaneSnapshot.from_dict(self._snapshot)

    def has_snapshot(self) -> bool:
        return self._snapshot is not None

    def clear_snapshot(self) -> None:
        self._snapshot = None

    # ------------------------------------------------------------------
    # replay
    # ------------------------------------------------------------------

    def replay_events(self) -> Dict[str, Any]:
        """
        Rebuild the latest known state from the event log.

        Returns:
            {
                "components":  {component_id: {"state": ..., "component_type": ...}},
                "system_state": SystemState,
                "trading_state": TradingState,
            }
        """
        components: Dict[str, Dict[str, str]] = {}
        system_state: SystemState = SystemState.INITIALIZING
        trading_state: TradingState = TradingState.TRADING_DISABLED

        for payload in self._events:
            event_type = payload.get("event_type")
            if event_type == "COMPONENT_STATE_CHANGED":
                components[payload["component_id"]] = {
                    "state": payload["new_state"],
                    "component_type": payload["component_type"],
                }
            elif event_type == "SYSTEM_STATE_CHANGED":
                system_state = SystemState(payload["new_state"])
            elif event_type == "TRADING_STATE_CHANGED":
                trading_state = TradingState(payload["new_state"])

        return {
            "components": components,
            "system_state": system_state,
            "trading_state": trading_state,
        }

    def rebuild_registry(self) -> ComponentRegistry:
        """
        Reconstruct a ComponentRegistry from persisted records + event log.

        Component records seed every registered component; the event log then
        overlays the latest state per component.  A component that never emitted
        a state change only lives in the records — so rebuild is exact when the
        records survive, and approximate (event-only) after a full wipe.
        """
        from ..domain.component_registry import ComponentType

        registry = ComponentRegistry()
        for data in self._components.values():
            info = ComponentInfo.from_dict(data)
            registry.register(
                component_id=info.component_id,
                component_type=info.component_type,
                version=info.version,
                state=info.state,
                criticality=info.criticality,
            )
        replay = self.replay_events()
        for component_id, meta in replay["components"].items():
            info = registry.get(component_id)
            if info is None:
                info = registry.register(
                    component_id=component_id,
                    component_type=ComponentType(meta["component_type"]),
                    version="1.0.0",
                )
            info.update_state(ComponentState(meta["state"]))
        return registry
