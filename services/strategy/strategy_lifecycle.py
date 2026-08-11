"""
Production strategy lifecycle manager.

Orchestrates the complete lifecycle of a strategy from creation
to archival, enforcing valid state transitions and emitting events
at each stage.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .strategy_event import StrategyEvent, StrategyEventPublisher, StrategyEventType
from .strategy_state import (
    StrategyLifecycleState,
    StateTransition,
    can_transition,
)

logger = logging.getLogger(__name__)


@dataclass
class LifecycleTransitionResult:
    """Result of a lifecycle transition attempt."""

    success: bool
    strategy_id: str
    from_state: StrategyLifecycleState
    to_state: StrategyLifecycleState
    duration_ms: float = 0.0
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "strategy_id": self.strategy_id,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "metadata": self.metadata,
        }


class StrategyLifecycleManager:
    """Manages the complete lifecycle of production strategies.

    Responsibilities:
        - Enforce valid state transitions
        - Execute pre/post transition hooks
        - Emit lifecycle events
        - Track transition history
        - Handle error recovery transitions
    """

    def __init__(
        self,
        event_publisher: Optional[StrategyEventPublisher] = None,
    ) -> None:
        # Strategy state storage: strategy_id → current state
        self._states: Dict[str, StrategyLifecycleState] = {}
        self._histories: Dict[str, list[StateTransition]] = {}

        self._event_publisher = event_publisher or StrategyEventPublisher()

        # Transition hooks: state → [before_hooks], [after_hooks]
        self._before_hooks: Dict[StrategyLifecycleState, list] = {
            s: [] for s in StrategyLifecycleState
        }
        self._after_hooks: Dict[StrategyLifecycleState, list] = {
            s: [] for s in StrategyLifecycleState
        }

        self._initialized: bool = False

    # ── Lifecycle ──

    async def initialize(self) -> None:
        await self._event_publisher.initialize()
        self._initialized = True
        logger.info("StrategyLifecycleManager initialized")

    async def shutdown(self) -> None:
        self._states.clear()
        self._histories.clear()
        await self._event_publisher.shutdown()
        self._initialized = False
        logger.info("StrategyLifecycleManager shut down")

    # ── Registration ──

    def register(
        self,
        strategy_id: str,
        initial_state: StrategyLifecycleState = StrategyLifecycleState.CREATED,
    ) -> None:
        """Register a strategy with the lifecycle manager."""
        self._states[strategy_id] = initial_state
        self._histories[strategy_id] = []
        logger.info(
            "Strategy %s registered with state: %s",
            strategy_id,
            initial_state.value,
        )

    def get_state(self, strategy_id: str) -> StrategyLifecycleState:
        """Get the current lifecycle state of a strategy."""
        if strategy_id not in self._states:
            raise KeyError(f"Strategy not registered: {strategy_id}")
        return self._states[strategy_id]

    def get_history(self, strategy_id: str) -> list[StateTransition]:
        """Get the transition history for a strategy."""
        return list(self._histories.get(strategy_id, []))

    # ── Hooks ──

    def on_before(
        self,
        state: StrategyLifecycleState,
        hook,
    ) -> None:
        """Register a hook to run before entering a state."""
        self._before_hooks[state].append(hook)

    def on_after(
        self,
        state: StrategyLifecycleState,
        hook,
    ) -> None:
        """Register a hook to run after entering a state."""
        self._after_hooks[state].append(hook)

    # ── Transitions ──

    async def transition(
        self,
        strategy_id: str,
        target_state: StrategyLifecycleState,
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LifecycleTransitionResult:
        """Execute a state transition for a strategy.

        Args:
            strategy_id: The strategy identifier.
            target_state: The desired target state.
            reason: Human-readable reason for the transition.
            metadata: Optional metadata for the transition.

        Returns:
            A LifecycleTransitionResult indicating success or failure.

        Raises:
            KeyError: If the strategy is not registered.
        """
        current_state = self.get_state(strategy_id)

        if current_state == target_state:
            return LifecycleTransitionResult(
                success=True,
                strategy_id=strategy_id,
                from_state=current_state,
                to_state=target_state,
            )

        # Validate transition
        if not can_transition(current_state, target_state):
            error = (
                f"Invalid transition: {current_state.value} → {target_state.value}"
            )
            logger.error("Transition rejected for %s: %s", strategy_id, error)
            return LifecycleTransitionResult(
                success=False,
                strategy_id=strategy_id,
                from_state=current_state,
                to_state=target_state,
                error=error,
                metadata=metadata or {},
            )

        start_time = time.monotonic()

        # Pre-transition hooks
        try:
            for hook in self._before_hooks.get(target_state, []):
                await hook(strategy_id, current_state, target_state, metadata)
        except Exception as e:
            logger.exception("Pre-transition hook failed for %s", strategy_id)
            return LifecycleTransitionResult(
                success=False,
                strategy_id=strategy_id,
                from_state=current_state,
                to_state=target_state,
                error=f"Pre-hook failed: {e}",
                metadata=metadata or {},
            )

        # Execute transition
        self._states[strategy_id] = target_state

        transition_record = StateTransition(
            strategy_id=strategy_id,
            from_state=current_state,
            to_state=target_state,
            reason=reason,
            metadata=metadata or {},
            duration_ms=(time.monotonic() - start_time) * 1000,
        )
        self._histories[strategy_id].append(transition_record)

        # Post-transition hooks
        for hook in self._after_hooks.get(target_state, []):
            try:
                await hook(strategy_id, current_state, target_state, metadata)
            except Exception as e:
                logger.error("Post-transition hook error for %s: %s", strategy_id, e)

        # Emit event
        event_type = self._state_to_event_type(target_state)
        if event_type:
            await self._event_publisher.publish(StrategyEvent(
                event_id=f"{strategy_id}-{target_state.value}-{int(time.time())}",
                event_type=event_type,
                strategy_id=strategy_id,
                data={
                    "from_state": current_state.value,
                    "to_state": target_state.value,
                    "reason": reason,
                    **(metadata or {}),
                },
            ))

        logger.info(
            "Strategy %s transition: %s → %s (%s) [%.1fms]",
            strategy_id,
            current_state.value,
            target_state.value,
            reason,
            transition_record.duration_ms,
        )

        return LifecycleTransitionResult(
            success=True,
            strategy_id=strategy_id,
            from_state=current_state,
            to_state=target_state,
            duration_ms=transition_record.duration_ms,
            metadata=metadata or {},
        )

    # ── Convenience Methods ──

    async def deploy(
        self,
        strategy_id: str,
        reason: str = "Deploying strategy",
    ) -> LifecycleTransitionResult:
        """Execute the full deployment pipeline: validated → registered → deployed."""
        state = self.get_state(strategy_id)

        if state == StrategyLifecycleState.VALIDATED:
            result = await self.transition(
                strategy_id,
                StrategyLifecycleState.REGISTERING,
                reason=reason,
            )
            if not result.success:
                return result
            state = StrategyLifecycleState.REGISTERING

        if state == StrategyLifecycleState.REGISTERING:
            result = await self.transition(
                strategy_id,
                StrategyLifecycleState.REGISTERED,
                reason=reason,
            )
            if not result.success:
                return result
            state = StrategyLifecycleState.REGISTERED

        if state == StrategyLifecycleState.REGISTERED:
            result = await self.transition(
                strategy_id,
                StrategyLifecycleState.DEPLOYING,
                reason=reason,
            )
            if not result.success:
                return result
            state = StrategyLifecycleState.DEPLOYING

        if state == StrategyLifecycleState.DEPLOYING:
            return await self.transition(
                strategy_id,
                StrategyLifecycleState.DEPLOYED,
                reason=reason,
            )

        return await self.transition(
            strategy_id,
            StrategyLifecycleState.DEPLOYED,
            reason=reason,
        )

    async def start(
        self,
        strategy_id: str,
        reason: str = "Starting strategy",
    ) -> LifecycleTransitionResult:
        """Start a deployed strategy."""
        state = self.get_state(strategy_id)

        if state == StrategyLifecycleState.DEPLOYED:
            result = await self.transition(
                strategy_id,
                StrategyLifecycleState.STARTING,
                reason=reason,
            )
            if not result.success:
                return result

        return await self.transition(
            strategy_id,
            StrategyLifecycleState.RUNNING,
            reason=reason,
        )

    async def stop(
        self,
        strategy_id: str,
        reason: str = "Stopping strategy",
    ) -> LifecycleTransitionResult:
        """Stop a running strategy."""
        state = self.get_state(strategy_id)

        if state in {StrategyLifecycleState.RUNNING, StrategyLifecycleState.PAUSED}:
            result = await self.transition(
                strategy_id,
                StrategyLifecycleState.STOPPING,
                reason=reason,
            )
            if not result.success:
                return result

        return await self.transition(
            strategy_id,
            StrategyLifecycleState.STOPPED,
            reason=reason,
        )

    async def pause(
        self,
        strategy_id: str,
        reason: str = "Pausing strategy",
    ) -> LifecycleTransitionResult:
        """Pause a running strategy."""
        result = await self.transition(
            strategy_id,
            StrategyLifecycleState.PAUSING,
            reason=reason,
        )
        if not result.success:
            return result

        return await self.transition(
            strategy_id,
            StrategyLifecycleState.PAUSED,
            reason=reason,
        )

    async def resume(
        self,
        strategy_id: str,
        reason: str = "Resuming strategy",
    ) -> LifecycleTransitionResult:
        """Resume a paused strategy."""
        result = await self.transition(
            strategy_id,
            StrategyLifecycleState.RESUMING,
            reason=reason,
        )
        if not result.success:
            return result

        return await self.transition(
            strategy_id,
            StrategyLifecycleState.RUNNING,
            reason=reason,
        )

    async def archive(
        self,
        strategy_id: str,
        reason: str = "Archiving strategy",
    ) -> LifecycleTransitionResult:
        """Archive a stopped strategy."""
        result = await self.transition(
            strategy_id,
            StrategyLifecycleState.ARCHIVING,
            reason=reason,
        )
        if not result.success:
            return result

        return await self.transition(
            strategy_id,
            StrategyLifecycleState.ARCHIVED,
            reason=reason,
        )

    # ── Helpers ──

    @staticmethod
    def _state_to_event_type(
        state: StrategyLifecycleState,
    ) -> Optional[StrategyEventType]:
        """Map a lifecycle state to its event type."""
        mapping = {
            StrategyLifecycleState.CREATED: None,
            StrategyLifecycleState.VALIDATED: StrategyEventType.STRATEGY_VALIDATED,
            StrategyLifecycleState.REGISTERED: StrategyEventType.STRATEGY_REGISTERED,
            StrategyLifecycleState.DEPLOYED: StrategyEventType.STRATEGY_DEPLOYED,
            StrategyLifecycleState.RUNNING: StrategyEventType.STRATEGY_STARTED,
            StrategyLifecycleState.PAUSED: StrategyEventType.STRATEGY_PAUSED,
            StrategyLifecycleState.RESUMING: None,
            StrategyLifecycleState.STOPPED: StrategyEventType.STRATEGY_STOPPED,
            StrategyLifecycleState.FAILED: StrategyEventType.STRATEGY_FAILED,
            StrategyLifecycleState.DEGRADED: StrategyEventType.STRATEGY_DEGRADED,
            StrategyLifecycleState.RECOVERING: None,
            StrategyLifecycleState.ARCHIVED: StrategyEventType.STRATEGY_ARCHIVED,
        }
        return mapping.get(state)

    @property
    def strategy_count(self) -> int:
        return len(self._states)

    def get_summary(self) -> Dict[str, Any]:
        state_counts: Dict[str, int] = {}
        for state in self._states.values():
            key = state.value
            state_counts[key] = state_counts.get(key, 0) + 1

        return {
            "total_strategies": self.strategy_count,
            "state_distribution": state_counts,
            "initialized": self._initialized,
        }
