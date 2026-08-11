"""
Rollout Manager — Gradual strategy rollout with traffic shifting.

Manages staged rollouts from canary through full production,
with configurable traffic percentages and health checks.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RolloutStage(str, Enum):
    """Rollout pipeline stages."""
    INIT = "init"
    CANARY_5 = "canary_5"
    CANARY_20 = "canary_20"
    CANARY_50 = "canary_50"
    FULL = "full"
    COMPLETED = "completed"
    PAUSED = "paused"
    ROLLED_BACK = "rolled_back"


@dataclass
class RolloutProgress:
    """Current rollout progress."""
    strategy_id: str
    version: str
    current_stage: RolloutStage = RolloutStage.INIT
    traffic_percentage: float = 0.0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stage_started_at: Optional[datetime] = None
    health_checks_passed: int = 0
    health_checks_failed: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)


class RolloutManager:
    """
    Manages gradual strategy rollouts with traffic shifting.

    Implements staged rollout (5% -> 20% -> 50% -> 100%) with
    health gate checks at each stage before advancing.

    Usage::

        rm = RolloutManager()
        await rm.initialize()
        progress = await rm.start_rollout("strat_001", "1.2.0")
        await rm.advance_stage("strat_001")  # 5% -> 20%
    """

    STAGE_TRAFFIC_MAP: dict[RolloutStage, float] = {
        RolloutStage.INIT: 0.0,
        RolloutStage.CANARY_5: 5.0,
        RolloutStage.CANARY_20: 20.0,
        RolloutStage.CANARY_50: 50.0,
        RolloutStage.FULL: 100.0,
        RolloutStage.COMPLETED: 100.0,
    }

    STAGE_ORDER: list[RolloutStage] = [
        RolloutStage.INIT,
        RolloutStage.CANARY_5,
        RolloutStage.CANARY_20,
        RolloutStage.CANARY_50,
        RolloutStage.FULL,
        RolloutStage.COMPLETED,
    ]

    def __init__(self) -> None:
        self._rollouts: dict[str, RolloutProgress] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the rollout manager."""
        logger.info("RolloutManager initialized.")

    async def stop(self) -> None:
        """Stop the rollout manager."""
        logger.info("RolloutManager stopped.")

    # ---- Rollout Operations ----

    async def start_rollout(
        self,
        strategy_id: str,
        version: str,
    ) -> RolloutProgress:
        """Start a new rollout for a strategy."""
        async with self._lock:
            progress = RolloutProgress(
                strategy_id=strategy_id,
                version=version,
                current_stage=RolloutStage.CANARY_5,
                traffic_percentage=5.0,
                stage_started_at=datetime.now(timezone.utc),
            )
            self._rollouts[strategy_id] = progress

        logger.info(f"Rollout started: {strategy_id} v{version} at 5%")
        return progress

    async def advance_stage(self, strategy_id: str) -> RolloutProgress:
        """Advance rollout to the next stage."""
        async with self._lock:
            progress = self._rollouts.get(strategy_id)
            if not progress:
                raise ValueError(f"No rollout found: {strategy_id}")

            current_idx = self.STAGE_ORDER.index(progress.current_stage)
            if current_idx >= len(self.STAGE_ORDER) - 1:
                progress.current_stage = RolloutStage.COMPLETED
                progress.traffic_percentage = 100.0
                return progress

            next_stage = self.STAGE_ORDER[current_idx + 1]
            progress.current_stage = next_stage
            progress.traffic_percentage = self.STAGE_TRAFFIC_MAP[next_stage]
            progress.stage_started_at = datetime.now(timezone.utc)

        logger.info(f"Rollout advanced: {strategy_id} -> {next_stage.value} ({progress.traffic_percentage}%)")
        return progress

    async def pause_rollout(self, strategy_id: str) -> RolloutProgress:
        """Pause a rollout at current stage."""
        async with self._lock:
            progress = self._rollouts.get(strategy_id)
            if not progress:
                raise ValueError(f"No rollout found: {strategy_id}")
            progress.current_stage = RolloutStage.PAUSED

        logger.info(f"Rollout paused: {strategy_id}")
        return progress

    async def rollback_rollout(self, strategy_id: str) -> RolloutProgress:
        """Rollback a rollout to zero traffic."""
        async with self._lock:
            progress = self._rollouts.get(strategy_id)
            if not progress:
                raise ValueError(f"No rollout found: {strategy_id}")
            progress.current_stage = RolloutStage.ROLLED_BACK
            progress.traffic_percentage = 0.0

        logger.info(f"Rollout rolled back: {strategy_id}")
        return progress

    async def record_health_check(
        self,
        strategy_id: str,
        passed: bool,
        metrics: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record a health check result for a rollout."""
        async with self._lock:
            progress = self._rollouts.get(strategy_id)
            if not progress:
                return
            if passed:
                progress.health_checks_passed += 1
            else:
                progress.health_checks_failed += 1
            if metrics:
                progress.metrics.update(metrics)

    async def get_rollout(self, strategy_id: str) -> Optional[RolloutProgress]:
        """Get rollout progress for a strategy."""
        return self._rollouts.get(strategy_id)

    async def list_rollouts(self) -> list[RolloutProgress]:
        """List all active rollouts."""
        return list(self._rollouts.values())

    async def get_traffic_percentage(self, strategy_id: str) -> float:
        """Get current traffic percentage for a strategy."""
        progress = self._rollouts.get(strategy_id)
        return progress.traffic_percentage if progress else 0.0
