"""
ICYQuant Rollout Manager — Orchestrates gradual model rollout across environments.

Handles phased traffic shifting, validation gate checks, progressive
promotion, and automated rollback during canary/rolling deployments.

Integrates with deployment strategy, canary controller, and monitoring.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .deployment_strategy import (
    StrategyExecution,
    StrategyPhase,
    StrategyType,
    TrafficStep,
    ValidationGate,
    create_strategy,
    BaseDeploymentStrategy,
)

if TYPE_CHECKING:
    from .deployment_manager import DeploymentManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RolloutStatus(str, Enum):
    """Status of a rollout execution."""
    PENDING = "pending"
    WARMING_UP = "warming_up"
    IN_PROGRESS = "in_progress"
    VALIDATING = "validating"
    STABILIZING = "stabilizing"
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled_back"
    ABORTED = "aborted"
    FAILED = "failed"
    COMPLETED = "completed"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RolloutConfig:
    """Rollout execution configuration."""
    model_id: str
    candidate_version: str
    strategy_type: StrategyType = StrategyType.CANARY
    traffic_steps: Optional[List[TrafficStep]] = None
    validation_gates: Optional[List[ValidationGate]] = None
    auto_promote: bool = False
    auto_rollback: bool = True
    max_duration_seconds: float = 86400.0
    warmup_seconds: float = 30.0
    stabilisation_seconds: float = 300.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RolloutState:
    """Runtime rollout execution state."""
    rollout_id: str
    model_id: str
    candidate_version: str
    status: RolloutStatus = RolloutStatus.PENDING
    current_step: int = 0
    total_steps: int = 0
    current_traffic_percent: float = 0.0
    started_at: Optional[str] = None
    step_started_at: Optional[str] = None
    completed_at: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        start = datetime.fromisoformat(self.started_at)
        return (datetime.now(timezone.utc) - start).total_seconds()

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            RolloutStatus.PROMOTED,
            RolloutStatus.ROLLED_BACK,
            RolloutStatus.ABORTED,
            RolloutStatus.FAILED,
            RolloutStatus.COMPLETED,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rollout_id": self.rollout_id,
            "model_id": self.model_id,
            "candidate_version": self.candidate_version,
            "status": self.status.value,
            "current_step": f"{self.current_step}/{self.total_steps}",
            "traffic_percent": self.current_traffic_percent,
            "duration_seconds": self.duration_seconds,
            "errors": self.errors[-5:] if self.errors else [],
        }


# ---------------------------------------------------------------------------
# Rollout Manager
# ---------------------------------------------------------------------------

class RolloutManager:
    """Manages the full rollout lifecycle.

    Coordinates:
      1. Warmup phase
      2. Progressive traffic shifting (step-by-step)
      3. Validation at each step
      4. Stabilisation periods
      5. Final promotion or rollback

    Usage::

        manager = RolloutManager(deployment_manager)
        state = await manager.start_rollout(config)
        while not state.is_terminal:
            state = await manager.progress(state.rollout_id)
            await asyncio.sleep(30)
        print(f"Rollout completed: {state.status}")
    """

    def __init__(
        self,
        deployment_manager: "DeploymentManager",
    ):
        self.deployment_manager = deployment_manager
        self._rollouts: Dict[str, RolloutState] = {}
        self._strategy_instances: Dict[str, BaseDeploymentStrategy] = {}
        self._active_rollouts: Dict[str, RolloutState] = {}
        self._initialized = False

        # Callbacks
        self._on_step: Optional[Callable[[RolloutState], None]] = None
        self._on_promote: Optional[Callable[[RolloutState], None]] = None
        self._on_rollback: Optional[Callable[[RolloutState, str], None]] = None

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("RolloutManager initialized")

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_step(self, callback: Callable[[RolloutState], None]) -> None:
        self._on_step = callback

    def on_promote(self, callback: Callable[[RolloutState], None]) -> None:
        self._on_promote = callback

    def on_rollback(self, callback: Callable[[RolloutState, str], None]) -> None:
        self._on_rollback = callback

    # ------------------------------------------------------------------
    # Rollout lifecycle
    # ------------------------------------------------------------------

    async def start_rollout(self, config: RolloutConfig) -> RolloutState:
        """Begin a new rollout.

        Steps:
          1. Create rollout state with traffic steps
          2. Load candidate model
          3. Start warmup
          4. Begin first traffic step

        Args:
            config: Rollout configuration.

        Returns:
            Initial rollout state.
        """
        strategy = create_strategy(config.strategy_type)
        strategy_config = strategy.get_config()

        # Merge user config with strategy defaults
        if config.traffic_steps:
            strategy_config.traffic_steps = config.traffic_steps
        if config.validation_gates:
            strategy_config.validation_gates = config.validation_gates

        rollout_id = str(uuid.uuid4())
        state = RolloutState(
            rollout_id=rollout_id,
            model_id=config.model_id,
            candidate_version=config.candidate_version,
            total_steps=len(strategy_config.traffic_steps),
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        self._rollouts[rollout_id] = state
        self._strategy_instances[rollout_id] = strategy

        # Start canary deployment via deployment manager
        initial_traffic = (
            strategy_config.traffic_steps[0].target_percent
            if strategy_config.traffic_steps
            else 5.0
        )

        try:
            state.status = RolloutStatus.WARMING_UP
            state.record_event("warmup_start", {"warmup_seconds": config.warmup_seconds})

            # Deploy as canary
            await self.deployment_manager.start_canary(
                model_id=config.model_id,
                candidate_version=config.candidate_version,
                traffic_percent=initial_traffic,
            )

            await asyncio.sleep(config.warmup_seconds)

            # Begin first step
            state.status = RolloutStatus.IN_PROGRESS
            state.current_step = 1
            state.current_traffic_percent = initial_traffic
            state.step_started_at = datetime.now(timezone.utc).isoformat()

            self._active_rollouts[rollout_id] = state
            state.record_event("rollout_started")

            logger.info(
                "Rollout started: %s@%s (step 1/%d, %.1f%%)",
                config.model_id, config.candidate_version,
                state.total_steps, initial_traffic,
            )

        except Exception as exc:
            state.status = RolloutStatus.FAILED
            state.errors.append(str(exc))
            logger.exception("Rollout start failed: %s", exc)
            raise

        return state

    async def progress(self, rollout_id: str) -> RolloutState:
        """Advance rollout to the next step or complete.

        Evaluates current step's validation gates and decides:
          - Next traffic step
          - Stabilisation
          - Promotion
          - Rollback

        Args:
            rollout_id: Rollout to progress.

        Returns:
            Updated rollout state.
        """
        state = self._rollouts.get(rollout_id)
        if state is None:
            raise ValueError(f"Rollout not found: {rollout_id}")

        if state.is_terminal:
            return state

        strategy = self._strategy_instances.get(rollout_id)
        if strategy is None:
            state.status = RolloutStatus.FAILED
            state.errors.append("Strategy instance not found")
            return state

        strategy_config = strategy.get_config()

        try:
            # Phase 1: Validate current step
            state.status = RolloutStatus.VALIDATING
            metrics = await self._collect_current_metrics(state)

            valid, reason = await strategy.validate(
                StrategyExecution(
                    execution_id=rollout_id,
                    model_id=state.model_id,
                    candidate_version=state.candidate_version,
                    strategy=strategy_config,
                    current_step_index=state.current_step - 1,
                )
            )
            state.record_event("validation", {"valid": valid, "reason": reason})

            if not valid and strategy_config.auto_rollback:
                await self._execute_rollback(state, f"Validation failed: {reason}")
                return state

            # Phase 2: Check promotion readiness
            should_promote, promotion_reason = await strategy.should_promote(
                StrategyExecution(
                    execution_id=rollout_id,
                    model_id=state.model_id,
                    candidate_version=state.candidate_version,
                    strategy=strategy_config,
                    current_step_index=state.current_step - 1,
                ),
                metrics,
            )

            if should_promote:
                return await self._execute_promotion(state)

            # Phase 3: Advance to next traffic step
            if state.current_step < state.total_steps:
                await self._advance_traffic(state, strategy_config)
            else:
                # All steps complete — stabilise then promote
                state.status = RolloutStatus.STABILIZING
                state.record_event("stabilising")
                await asyncio.sleep(strategy_config.cooldown_seconds)
                return await self._execute_promotion(state)

        except Exception as exc:
            state.errors.append(str(exc))
            logger.exception("Rollout progress failed: %s", exc)
            if state.status != RolloutStatus.ROLLED_BACK:
                state.status = RolloutStatus.FAILED

        return state

    async def abort_rollout(self, rollout_id: str, reason: str = "Manual abort") -> RolloutState:
        """Abort an in-progress rollout."""
        state = self._rollouts.get(rollout_id)
        if state is None:
            raise ValueError(f"Rollout not found: {rollout_id}")

        if state.is_terminal:
            return state

        return await self._execute_rollback(state, reason)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_state(self, rollout_id: str) -> Optional[RolloutState]:
        """Get rollout state by ID."""
        return self._rollouts.get(rollout_id)

    def list_active(self) -> List[RolloutState]:
        """List all active rollouts."""
        return list(self._active_rollouts.values())

    def list_all(self) -> List[RolloutState]:
        """List all rollouts."""
        return list(self._rollouts.values())

    def get_history(self, model_id: str) -> List[Dict[str, Any]]:
        """Get rollout history for a model."""
        return [
            s.to_dict() for s in self._rollouts.values()
            if s.model_id == model_id
        ]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _advance_traffic(
        self,
        state: RolloutState,
        strategy_config: Any,
    ) -> None:
        """Move to the next traffic step."""
        next_step_idx = state.current_step  # 0-based for list access
        if next_step_idx >= len(strategy_config.traffic_steps):
            return

        next_step = strategy_config.traffic_steps[next_step_idx]
        step_duration = next_step.duration_seconds

        state.current_step += 1
        state.current_traffic_percent = next_step.target_percent
        state.step_started_at = datetime.now(timezone.utc).isoformat()
        state.status = RolloutStatus.IN_PROGRESS

        # Update deployment manager traffic
        await self.deployment_manager.update_canary_traffic(
            model_id=state.model_id,
            traffic_percent=next_step.target_percent,
        )

        state.record_event("traffic_shifted", {
            "step": state.current_step,
            "percent": next_step.target_percent,
        })

        if self._on_step:
            self._on_step(state)

        # Wait for stabilisation period
        if step_duration > 0:
            state.status = RolloutStatus.STABILIZING
            await asyncio.sleep(step_duration)
            state.status = RolloutStatus.IN_PROGRESS

    async def _execute_promotion(self, state: RolloutState) -> RolloutState:
        """Promote candidate to full production."""
        logger.info(
            "Promoting %s@%s to production",
            state.model_id, state.candidate_version,
        )

        await self.deployment_manager.promote_canary(state.model_id)

        state.status = RolloutStatus.PROMOTED
        state.current_traffic_percent = 100.0
        state.completed_at = datetime.now(timezone.utc).isoformat()
        state.record_event("promoted")

        self._active_rollouts.pop(state.rollout_id, None)

        if self._on_promote:
            self._on_promote(state)

        return state

    async def _execute_rollback(
        self, state: RolloutState, reason: str
    ) -> RolloutState:
        """Rollback to previous version."""
        logger.warning(
            "Rolling back %s@%s: %s",
            state.model_id, state.candidate_version, reason,
        )

        try:
            await self.deployment_manager.abort_canary(state.model_id)
        except Exception:
            logger.exception("Canary abort failed during rollback")

        state.status = RolloutStatus.ROLLED_BACK
        state.completed_at = datetime.now(timezone.utc).isoformat()
        state.errors.append(reason)
        state.record_event("rolled_back", {"reason": reason})

        self._active_rollouts.pop(state.rollout_id, None)

        if self._on_rollback:
            self._on_rollback(state, reason)

        return state

    async def _collect_current_metrics(
        self, state: RolloutState
    ) -> Dict[str, Any]:
        """Collect metrics for current rollout step.

        In production, this would query a metrics store / monitoring system.
        """
        return {
            "model_id": state.model_id,
            "candidate_version": state.candidate_version,
            "traffic_percent": state.current_traffic_percent,
            "step": state.current_step,
            "duration_seconds": state.duration_seconds,
            # These would come from monitoring in production
            "error_rate": 0.0,
            "p99_latency_ms": 50.0,
        }

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        active = len(self._active_rollouts)
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "active_rollouts": active,
            "total_rollouts": len(self._rollouts),
            "promoted": sum(
                1 for s in self._rollouts.values()
                if s.status == RolloutStatus.PROMOTED
            ),
            "rolled_back": sum(
                1 for s in self._rollouts.values()
                if s.status == RolloutStatus.ROLLED_BACK
            ),
        }

    def __repr__(self) -> str:
        return (
            f"RolloutManager(active={len(self._active_rollouts)}, "
            f"total={len(self._rollouts)})"
        )


# ---------------------------------------------------------------------------
# Extend RolloutState with event recording
# ---------------------------------------------------------------------------

def _add_event_method(cls):
    """Add record_event method to RolloutState."""
    def record_event(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
        self.history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "step": self.current_step,
            "traffic_percent": self.current_traffic_percent,
            "data": data or {},
        })
    cls.record_event = record_event

_add_event_method(RolloutState)
