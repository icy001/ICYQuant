"""
UpdateComponentState — apply a component state change and produce the
COMPONENT_STATE_CHANGED event (when the state actually changed).

The command never touches system/trading state itself; the Control Plane
service re-runs evaluation after the change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ..domain.component_registry import ComponentInfo, ComponentRegistry
from ..domain.component_state import ComponentState
from ..domain.system_state import StateReasonCode
from ..events.component_state_changed import ComponentStateChanged


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class UpdateComponentStateResult:
    """Outcome of applying an UpdateComponentState command."""

    component_id: str
    previous_state: Optional[ComponentState]
    new_state: ComponentState
    changed: bool
    event: Optional[ComponentStateChanged] = None


@dataclass
class UpdateComponentState:
    """Command: set a component to a new state, returning the event to emit."""

    component_id: str
    new_state: ComponentState
    reason: StateReasonCode
    at: Optional[datetime] = None
    detail: str = ""

    def execute(self, registry: ComponentRegistry) -> UpdateComponentStateResult:
        at = self.at or _utcnow()
        info: Optional[ComponentInfo] = registry.get(self.component_id)
        if info is None:
            raise ValueError(
                f"Unknown component '{self.component_id}' — register it first"
            )

        previous = info.state
        changed = registry.update_state(self.component_id, self.new_state, at)[1]
        if not changed:
            return UpdateComponentStateResult(
                component_id=self.component_id,
                previous_state=previous,
                new_state=self.new_state,
                changed=False,
            )

        event = ComponentStateChanged.from_change(
            component_id=self.component_id,
            component_type=info.component_type,
            previous_state=previous,
            new_state=self.new_state,
            reason=self.reason,
            detail=self.detail,
            occurred_at=at,
        )
        return UpdateComponentStateResult(
            component_id=self.component_id,
            previous_state=previous,
            new_state=self.new_state,
            changed=True,
            event=event,
        )


def update_component_state(
    registry: ComponentRegistry,
    component_id: str,
    new_state: ComponentState,
    reason: StateReasonCode,
    at: Optional[datetime] = None,
) -> UpdateComponentStateResult:
    """Convenience wrapper around the UpdateComponentState command."""
    return UpdateComponentState(
        component_id=component_id,
        new_state=new_state,
        reason=reason,
        at=at,
    ).execute(registry)
