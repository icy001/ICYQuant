"""
Strategy Lifecycle Controller — State machine and transition management.

Manages the complete lifecycle of production strategies from registration
through deployment, runtime, and eventual retirement.
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
    """Strategy lifecycle states."""
    CREATED = "created"
    VALIDATED = "validated"
    REGISTERED = "registered"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    STARTING = "starting"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    RESUMING = "resuming"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"
    ARCHIVED = "archived"
    DELETED = "deleted"


class LifecycleAction(str, Enum):
    """Actions that trigger lifecycle transitions."""
    CREATE = "create"
    VALIDATE = "validate"
    REGISTER = "register"
    DEPLOY = "deploy"
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    FAIL = "fail"
    RECOVER = "recover"
    ROLLBACK = "rollback"
    ARCHIVE = "archive"
    DELETE = "delete"


@dataclass
class LifecycleTransition:
    """Record of a lifecycle state transition."""
    strategy_id: str
    from_state: LifecycleState
    to_state: LifecycleState
    action: LifecycleAction
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyLifecycle:
    """Tracks a single strategy's lifecycle."""
    strategy_id: str
    current_state: LifecycleState = LifecycleState.CREATED
    history: list[LifecycleTransition] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# Valid transitions: {current_state: {action: next_state}}
TRANSITION_TABLE: dict[LifecycleState, dict[LifecycleAction, LifecycleState]] = {
    LifecycleState.CREATED: {
        LifecycleAction.VALIDATE: LifecycleState.VALIDATED,
        LifecycleAction.REGISTER: LifecycleState.REGISTERED,
        LifecycleAction.DELETE: LifecycleState.DELETED,
    },
    LifecycleState.VALIDATED: {
        LifecycleAction.REGISTER: LifecycleState.REGISTERED,
        LifecycleAction.FAIL: LifecycleState.FAILED,
        LifecycleAction.DELETE: LifecycleState.DELETED,
    },
    LifecycleState.REGISTERED: {
        LifecycleAction.DEPLOY: LifecycleState.DEPLOYING,
        LifecycleAction.ARCHIVE: LifecycleState.ARCHIVED,
        LifecycleAction.DELETE: LifecycleState.DELETED,
    },
    LifecycleState.DEPLOYING: {
        LifecycleAction.DEPLOY: LifecycleState.DEPLOYED,
        LifecycleAction.FAIL: LifecycleState.FAILED,
        LifecycleAction.ROLLBACK: LifecycleState.ROLLING_BACK,
    },
    LifecycleState.DEPLOYED: {
        LifecycleAction.START: LifecycleState.STARTING,
        LifecycleAction.ARCHIVE: LifecycleState.ARCHIVED,
        LifecycleAction.DELETE: LifecycleState.DELETED,
    },
    LifecycleState.STARTING: {
        LifecycleAction.START: LifecycleState.RUNNING,
        LifecycleAction.FAIL: LifecycleState.FAILED,
    },
    LifecycleState.RUNNING: {
        LifecycleAction.PAUSE: LifecycleState.PAUSING,
        LifecycleAction.STOP: LifecycleState.STOPPING,
        LifecycleAction.FAIL: LifecycleState.FAILED,
    },
    LifecycleState.PAUSING: {
        LifecycleAction.PAUSE: LifecycleState.PAUSED,
        LifecycleAction.FAIL: LifecycleState.FAILED,
    },
    LifecycleState.PAUSED: {
        LifecycleAction.RESUME: LifecycleState.RESUMING,
        LifecycleAction.STOP: LifecycleState.STOPPING,
        LifecycleAction.FAIL: LifecycleState.FAILED,
    },
    LifecycleState.RESUMING: {
        LifecycleAction.RESUME: LifecycleState.RUNNING,
        LifecycleAction.FAIL: LifecycleState.FAILED,
    },
    LifecycleState.STOPPING: {
        LifecycleAction.STOP: LifecycleState.STOPPED,
        LifecycleAction.FAIL: LifecycleState.FAILED,
    },
    LifecycleState.STOPPED: {
        LifecycleAction.START: LifecycleState.STARTING,
        LifecycleAction.ARCHIVE: LifecycleState.ARCHIVED,
        LifecycleAction.DELETE: LifecycleState.DELETED,
    },
    LifecycleState.FAILED: {
        LifecycleAction.RECOVER: LifecycleState.STOPPED,
        LifecycleAction.ROLLBACK: LifecycleState.ROLLING_BACK,
        LifecycleAction.DELETE: LifecycleState.DELETED,
    },
    LifecycleState.ROLLING_BACK: {
        LifecycleAction.ROLLBACK: LifecycleState.DEPLOYED,
        LifecycleAction.FAIL: LifecycleState.FAILED,
    },
    LifecycleState.ARCHIVED: {
        LifecycleAction.DELETE: LifecycleState.DELETED,
    },
}


class LifecycleController:
    """
    Strategy lifecycle state machine.

    Enforces valid state transitions, records full transition history,
    and emits lifecycle events for auditing and observability.

    Usage::

        lc = LifecycleController(event_bridge=events, audit_center=audit)
        await lc.initialize()
        transition = await lc.transition("strat_001", LifecycleAction.DEPLOY)
    """

    def __init__(
        self,
        event_bridge: Any = None,
        audit_center: Any = None,
    ) -> None:
        self._event_bridge = event_bridge
        self._audit_center = audit_center
        self._lifecycles: dict[str, StrategyLifecycle] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the lifecycle controller."""
        logger.info("LifecycleController initialized.")

    async def stop(self) -> None:
        """Stop the lifecycle controller."""
        logger.info("LifecycleController stopped.")

    # ---- Lifecycle Management ----

    async def create_lifecycle(self, strategy_id: str) -> StrategyLifecycle:
        """Create a new lifecycle for a strategy."""
        async with self._lock:
            if strategy_id in self._lifecycles:
                return self._lifecycles[strategy_id]
            lifecycle = StrategyLifecycle(strategy_id=strategy_id)
            self._lifecycles[strategy_id] = lifecycle
            logger.info(f"Lifecycle created: {strategy_id}")
            return lifecycle

    async def transition(
        self,
        strategy_id: str,
        action: LifecycleAction,
        reason: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> LifecycleTransition:
        """Execute a lifecycle state transition."""
        async with self._lock:
            lifecycle = self._lifecycles.get(strategy_id)
            if not lifecycle:
                lifecycle = await self.create_lifecycle(strategy_id)

            current = lifecycle.current_state
            transitions = TRANSITION_TABLE.get(current, {})
            next_state = transitions.get(action)

            if next_state is None:
                raise ValueError(
                    f"Invalid transition: {current} -> {action}. "
                    f"Valid actions from {current}: {list(transitions.keys())}"
                )

            t = LifecycleTransition(
                strategy_id=strategy_id,
                from_state=current,
                to_state=next_state,
                action=action,
                reason=reason,
                metadata=metadata or {},
            )

            lifecycle.current_state = next_state
            lifecycle.history.append(t)
            lifecycle.updated_at = t.timestamp

            logger.info(f"Lifecycle transition: {strategy_id} {current} -> {next_state} ({action})")

            await self._emit_event("strategy.lifecycle.transition", {
                "strategy_id": strategy_id,
                "from_state": current.value,
                "to_state": next_state.value,
                "action": action.value,
                "reason": reason,
            })

            await self._audit(
                f"strategy.lifecycle.{action.value}",
                f"Strategy {strategy_id}: {current.value} -> {next_state.value} ({action.value})",
            )

            return t

    async def get_lifecycle(self, strategy_id: str) -> Optional[StrategyLifecycle]:
        """Get a strategy's lifecycle state."""
        return self._lifecycles.get(strategy_id)

    async def get_state(self, strategy_id: str) -> Optional[LifecycleState]:
        """Get current lifecycle state for a strategy."""
        lifecycle = self._lifecycles.get(strategy_id)
        return lifecycle.current_state if lifecycle else None

    async def get_history(self, strategy_id: str) -> list[LifecycleTransition]:
        """Get transition history for a strategy."""
        lifecycle = self._lifecycles.get(strategy_id)
        return lifecycle.history.copy() if lifecycle else []

    async def is_valid_transition(
        self,
        strategy_id: str,
        action: LifecycleAction,
    ) -> bool:
        """Check if a transition is valid for a strategy's current state."""
        lifecycle = self._lifecycles.get(strategy_id)
        if not lifecycle:
            return action == LifecycleAction.CREATE
        transitions = TRANSITION_TABLE.get(lifecycle.current_state, {})
        return action in transitions

    async def list_lifecycles(self) -> dict[str, LifecycleState]:
        """Get current state for all strategies."""
        return {sid: lc.current_state for sid, lc in self._lifecycles.items()}

    # ---- Internal ----

    async def _emit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_bridge:
            try:
                await self._event_bridge.emit(event_type, payload)
            except Exception as e:
                logger.error(f"Event emit failed: {e}")

    async def _audit(self, category: str, message: str) -> None:
        if self._audit_center:
            try:
                await self._audit_center.record(category=category, message=message)
            except Exception as e:
                logger.error(f"Audit failed: {e}")
