"""
Risk State — Risk component state management and persistence.

Tracks the operational state of all risk platform components
with serialization, comparison, and state transition recording.
"""

from __future__ import annotations

import asyncio
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StateStatus(str, Enum):
    """State operational status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    ERROR = "error"


@dataclass
class RiskState:
    """Operational state of a risk component."""
    component_id: str
    status: StateStatus = StateStatus.ACTIVE
    enabled: bool = True
    version: str = "1.0.0"
    last_evaluated_at: Optional[datetime] = None
    last_updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active_since: Optional[datetime] = None
    evaluation_count: int = 0
    failure_count: int = 0
    attributes: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StateTransition:
    """Record of a state change."""
    component_id: str
    from_status: StateStatus
    to_status: StateStatus
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RiskStateManager:
    """
    Manages operational state for all risk platform components.

    Tracks enabled/disabled status, evaluation counts, failure rates,
    and provides state serialization for snapshot-based recovery.

    Usage::

        mgr = RiskStateManager()
        await mgr.initialize()
        state = await mgr.create_state("check_position_limit")
        await mgr.record_evaluation("check_position_limit", success=True)
    """

    def __init__(self) -> None:
        self._states: dict[str, RiskState] = {}
        self._transitions: list[StateTransition] = []
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the state manager."""
        logger.info("RiskStateManager initialized.")

    async def stop(self) -> None:
        """Stop the state manager."""
        logger.info("RiskStateManager stopped.")

    # ---- State Management ----

    async def create_state(self, component_id: str) -> RiskState:
        """Create initial state for a component."""
        async with self._lock:
            if component_id in self._states:
                return self._states[component_id]
            state = RiskState(component_id=component_id)
            self._states[component_id] = state
        logger.debug(f"State created: {component_id}")
        return state

    async def get_state(self, component_id: str) -> Optional[RiskState]:
        """Get current state for a component."""
        return self._states.get(component_id)

    async def update_state(self, component_id: str, **kwargs: Any) -> Optional[RiskState]:
        """Update state attributes."""
        async with self._lock:
            state = self._states.get(component_id)
            if not state:
                return None
            for key, value in kwargs.items():
                if hasattr(state, key):
                    setattr(state, key, value)
            state.last_updated_at = datetime.now(timezone.utc)
        return state

    async def delete_state(self, component_id: str) -> bool:
        """Delete a component's state."""
        async with self._lock:
            if component_id in self._states:
                del self._states[component_id]
                return True
            return False

    # ---- State Transitions ----

    async def set_status(
        self,
        component_id: str,
        status: StateStatus,
        reason: str = "",
    ) -> Optional[RiskState]:
        """Change a component's operational status."""
        async with self._lock:
            state = self._states.get(component_id)
            if not state:
                return None

            old_status = state.status
            if old_status == status:
                return state

            transition = StateTransition(
                component_id=component_id,
                from_status=old_status,
                to_status=status,
                reason=reason,
            )
            self._transitions.append(transition)

            state.status = status
            state.last_updated_at = transition.timestamp

        logger.info(f"State transition: {component_id} {old_status.value} -> {status.value}")
        return state

    async def enable(self, component_id: str) -> Optional[RiskState]:
        """Enable a component."""
        return await self.update_state(component_id, enabled=True)

    async def disable(self, component_id: str) -> Optional[RiskState]:
        """Disable a component."""
        return await self.update_state(component_id, enabled=False)

    # ---- Tracking ----

    async def record_evaluation(self, component_id: str, success: bool) -> None:
        """Record an evaluation result."""
        async with self._lock:
            state = self._states.get(component_id)
            if state:
                state.evaluation_count += 1
                state.last_evaluated_at = datetime.now(timezone.utc)
                if not success:
                    state.failure_count += 1

    # ---- Query ----

    async def list_active(self) -> list[RiskState]:
        """List all active component states."""
        return [s for s in self._states.values() if s.status == StateStatus.ACTIVE and s.enabled]

    async def list_all(self) -> list[RiskState]:
        """List all component states."""
        return list(self._states.values())

    async def get_transitions(
        self,
        component_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[StateTransition]:
        """Get state transition history."""
        results = self._transitions
        if component_id:
            results = [t for t in results if t.component_id == component_id]
        return results[-limit:]

    async def snapshot(self) -> dict[str, Any]:
        """Export all states as a snapshot."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "states": {
                cid: {
                    "status": s.status.value,
                    "enabled": s.enabled,
                    "version": s.version,
                    "evaluation_count": s.evaluation_count,
                    "failure_count": s.failure_count,
                    "attributes": deepcopy(s.attributes),
                }
                for cid, s in self._states.items()
            },
        }

    async def restore(self, snapshot_data: dict[str, Any]) -> None:
        """Restore states from a snapshot."""
        states_data = snapshot_data.get("states", {})
        for cid, data in states_data.items():
            if cid in self._states:
                self._states[cid].status = StateStatus(data.get("status", "active"))
                self._states[cid].enabled = data.get("enabled", True)
                self._states[cid].attributes = deepcopy(data.get("attributes", {}))
        logger.info(f"Restored {len(states_data)} state(s) from snapshot.")

    async def health_check(self) -> dict[str, Any]:
        """Check state manager health."""
        return {
            "status": "healthy",
            "total_states": len(self._states),
            "active_states": len(await self.list_active()),
        }
