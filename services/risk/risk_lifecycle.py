"""
Risk Lifecycle Manager — Lifecycle state machine for risk components.

Manages the complete lifecycle of risk policies and components
from creation through initialization, runtime, pause, recovery,
and archival.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LifecycleState(str, Enum):
    """Risk component lifecycle states."""
    CREATED = "created"
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    RECOVERING = "recovering"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    ARCHIVED = "archived"


class LifecycleAction(str, Enum):
    """Actions that trigger lifecycle transitions."""
    CREATE = "create"
    INITIALIZE = "initialize"
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    FAIL = "fail"
    RECOVER = "recover"
    ARCHIVE = "archive"


@dataclass
class LifecycleTransition:
    """Record of a lifecycle state transition."""
    component_id: str
    from_state: LifecycleState
    to_state: LifecycleState
    action: LifecycleAction
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComponentLifecycle:
    """Tracks a single component's lifecycle."""
    component_id: str
    current_state: LifecycleState = LifecycleState.CREATED
    history: list[LifecycleTransition] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# Valid transition table
TRANSITIONS: dict[LifecycleState, dict[LifecycleAction, LifecycleState]] = {
    LifecycleState.CREATED: {
        LifecycleAction.INITIALIZE: LifecycleState.INITIALIZED,
        LifecycleAction.ARCHIVE: LifecycleState.ARCHIVED,
    },
    LifecycleState.INITIALIZED: {
        LifecycleAction.START: LifecycleState.RUNNING,
        LifecycleAction.ARCHIVE: LifecycleState.ARCHIVED,
    },
    LifecycleState.RUNNING: {
        LifecycleAction.PAUSE: LifecycleState.PAUSED,
        LifecycleAction.STOP: LifecycleState.STOPPING,
        LifecycleAction.FAIL: LifecycleState.FAILED,
    },
    LifecycleState.PAUSED: {
        LifecycleAction.RESUME: LifecycleState.RUNNING,
        LifecycleAction.STOP: LifecycleState.STOPPING,
        LifecycleAction.FAIL: LifecycleState.FAILED,
    },
    LifecycleState.RECOVERING: {
        LifecycleAction.RECOVER: LifecycleState.RUNNING,
        LifecycleAction.FAIL: LifecycleState.FAILED,
    },
    LifecycleState.STOPPING: {
        LifecycleAction.STOP: LifecycleState.STOPPED,
    },
    LifecycleState.STOPPED: {
        LifecycleAction.START: LifecycleState.RUNNING,
        LifecycleAction.ARCHIVE: LifecycleState.ARCHIVED,
    },
    LifecycleState.FAILED: {
        LifecycleAction.RECOVER: LifecycleState.RECOVERING,
        LifecycleAction.ARCHIVE: LifecycleState.ARCHIVED,
    },
}


class RiskLifecycle:
    """
    Lifecycle state machine for risk platform components.

    Manages the complete lifecycle: Created → Initialized → Running
    → Paused → Recovery → Archived, with strict transition validation.

    Usage::

        lc = RiskLifecycle()
        await lc.initialize()
        await lc.create_component("policy_position_limit")
        await lc.transition("policy_position_limit", LifecycleAction.INITIALIZE)
        await lc.transition("policy_position_limit", LifecycleAction.START)
    """

    def __init__(self) -> None:
        self._components: dict[str, ComponentLifecycle] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the lifecycle manager."""
        logger.info("RiskLifecycle initialized.")

    async def stop(self) -> None:
        """Stop the lifecycle manager."""
        logger.info("RiskLifecycle stopped.")

    # ---- Component Management ----

    async def create_component(self, component_id: str) -> ComponentLifecycle:
        """Create a new lifecycle component."""
        async with self._lock:
            if component_id in self._components:
                return self._components[component_id]
            lifecycle = ComponentLifecycle(component_id=component_id)
            self._components[component_id] = lifecycle
        logger.info(f"Lifecycle component created: {component_id}")
        return lifecycle

    async def transition(
        self,
        component_id: str,
        action: LifecycleAction,
        reason: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> LifecycleTransition:
        """Execute a lifecycle state transition."""
        async with self._lock:
            lifecycle = self._components.get(component_id)
            if not lifecycle:
                lifecycle = await self.create_component(component_id)

            current = lifecycle.current_state
            valid = TRANSITIONS.get(current, {})
            next_state = valid.get(action)

            if next_state is None:
                raise ValueError(
                    f"Invalid transition: {current.value} -> {action.value}. "
                    f"Valid from {current.value}: {list(valid.keys())}"
                )

            t = LifecycleTransition(
                component_id=component_id,
                from_state=current,
                to_state=next_state,
                action=action,
                reason=reason,
                metadata=metadata or {},
            )

            lifecycle.current_state = next_state
            lifecycle.history.append(t)
            lifecycle.updated_at = t.timestamp

        logger.info(f"Lifecycle: {component_id} {current.value} -> {next_state.value}")
        return t

    async def get_state(self, component_id: str) -> Optional[LifecycleState]:
        """Get current lifecycle state."""
        lifecycle = self._components.get(component_id)
        return lifecycle.current_state if lifecycle else None

    async def get_history(self, component_id: str) -> list[LifecycleTransition]:
        """Get transition history."""
        lifecycle = self._components.get(component_id)
        return lifecycle.history.copy() if lifecycle else []

    async def list_components(self) -> dict[str, LifecycleState]:
        """List all components and their states."""
        return {cid: lc.current_state for cid, lc in self._components.items()}

    async def health_check(self) -> dict[str, Any]:
        """Check lifecycle health."""
        states = await self.list_components()
        return {
            "total_components": len(states),
            "running": sum(1 for s in states.values() if s == LifecycleState.RUNNING),
            "paused": sum(1 for s in states.values() if s == LifecycleState.PAUSED),
            "failed": sum(1 for s in states.values() if s == LifecycleState.FAILED),
        }
