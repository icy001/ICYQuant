"""
Canary Manager — Canary deployment and analysis for strategies.

Manages canary deployments with A/B comparison, metric collection,
and automated promotion/rollback decisions.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CanaryStage(str, Enum):
    """Canary deployment stages."""
    INITIALIZING = "initializing"
    WARMING_UP = "warming_up"
    COLLECTING = "collecting"
    ANALYZING = "analyzing"
    PROMOTING = "promoting"
    ROLLING_BACK = "rolling_back"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CanaryConfig:
    """Canary deployment configuration."""
    canary_percentage: float = 5.0
    warmup_minutes: int = 10
    analysis_minutes: int = 60
    metrics_comparison_window_hours: int = 24
    max_regression_pct: float = 10.0  # Max allowed performance regression %
    auto_promote: bool = False
    auto_rollback: bool = True
    rollback_on_error_rate: float = 5.0  # Error rate threshold %


@dataclass
class CanaryMetrics:
    """Metrics collected during canary deployment."""
    canary_version: str
    baseline_version: str
    stage: CanaryStage = CanaryStage.INITIALIZING
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Performance metrics
    canary_sharpe: float = 0.0
    baseline_sharpe: float = 0.0
    canary_win_rate: float = 0.0
    baseline_win_rate: float = 0.0
    canary_error_rate: float = 0.0
    baseline_error_rate: float = 0.0
    canary_latency_p99_ms: float = 0.0
    baseline_latency_p99_ms: float = 0.0
    # Decision
    promote_ready: bool = False
    rollback_recommended: bool = False
    recommendation_reason: str = ""


class CanaryManager:
    """
    Manages canary deployments for production strategies.

    Supports progressive traffic shifting, A/B metric comparison,
    and automated promote/rollback decisions based on configurable
    regression thresholds.

    Usage::

        cm = CanaryManager()
        await cm.initialize()
        metrics = await cm.start_canary("strat_001", "1.2.0", "1.1.0", config)
        await cm.evaluate_canary("strat_001")  # -> promote or rollback
    """

    def __init__(self) -> None:
        self._canaries: dict[str, CanaryMetrics] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the canary manager."""
        logger.info("CanaryManager initialized.")

    async def stop(self) -> None:
        """Stop the canary manager."""
        logger.info("CanaryManager stopped.")

    # ---- Canary Operations ----

    async def start_canary(
        self,
        strategy_id: str,
        canary_version: str,
        baseline_version: str,
        config: Optional[CanaryConfig] = None,
    ) -> CanaryMetrics:
        """Start a canary deployment for a strategy."""
        async with self._lock:
            metrics = CanaryMetrics(
                canary_version=canary_version,
                baseline_version=baseline_version,
            )
            self._canaries[strategy_id] = metrics

        logger.info(f"Canary started: {strategy_id} canary={canary_version} baseline={baseline_version}")
        return metrics

    async def update_metrics(
        self,
        strategy_id: str,
        **metrics: Any,
    ) -> CanaryMetrics:
        """Update canary metrics with latest observations."""
        async with self._lock:
            canary = self._canaries.get(strategy_id)
            if not canary:
                raise ValueError(f"No canary found: {strategy_id}")

            for key, value in metrics.items():
                if hasattr(canary, key):
                    setattr(canary, key, value)

        return canary

    async def evaluate_canary(
        self,
        strategy_id: str,
        config: Optional[CanaryConfig] = None,
    ) -> CanaryMetrics:
        """Evaluate canary and make promote/rollback recommendation."""
        config = config or CanaryConfig()

        async with self._lock:
            canary = self._canaries.get(strategy_id)
            if not canary:
                raise ValueError(f"No canary found: {strategy_id}")

            canary.stage = CanaryStage.ANALYZING

            # Compare Sharpe
            sharpe_regression = 0.0
            if canary.baseline_sharpe > 0:
                sharpe_regression = ((canary.baseline_sharpe - canary.canary_sharpe) / canary.baseline_sharpe) * 100

            # Check error rate
            error_regression = canary.canary_error_rate - canary.baseline_error_rate

            # Decision logic
            if sharpe_regression > config.max_regression_pct:
                canary.rollback_recommended = True
                canary.recommendation_reason = f"Sharpe regression {sharpe_regression:.1f}% exceeds {config.max_regression_pct}% threshold"
                canary.stage = CanaryStage.FAILED
            elif error_regression > config.rollback_on_error_rate:
                canary.rollback_recommended = True
                canary.recommendation_reason = f"Error rate increased by {error_regression:.1f}%"
                canary.stage = CanaryStage.FAILED
            else:
                canary.promote_ready = True
                canary.recommendation_reason = "All metrics within acceptable thresholds"
                canary.stage = CanaryStage.COMPLETED

            # Auto actions
            if canary.rollback_recommended and config.auto_rollback:
                canary.stage = CanaryStage.ROLLING_BACK
                logger.warning(f"Auto-rollback: {strategy_id} - {canary.recommendation_reason}")
            elif canary.promote_ready and config.auto_promote:
                canary.stage = CanaryStage.PROMOTING
                logger.info(f"Auto-promote: {strategy_id}")

        return canary

    async def promote_canary(self, strategy_id: str) -> CanaryMetrics:
        """Manually promote a canary to full production."""
        async with self._lock:
            canary = self._canaries.get(strategy_id)
            if not canary:
                raise ValueError(f"No canary found: {strategy_id}")
            canary.stage = CanaryStage.PROMOTING
            canary.promote_ready = True

        logger.info(f"Canary promoted: {strategy_id}")
        return canary

    async def rollback_canary(self, strategy_id: str) -> CanaryMetrics:
        """Rollback a canary deployment."""
        async with self._lock:
            canary = self._canaries.get(strategy_id)
            if not canary:
                raise ValueError(f"No canary found: {strategy_id}")
            canary.stage = CanaryStage.ROLLING_BACK

        logger.info(f"Canary rolled back: {strategy_id}")
        return canary

    async def get_canary(self, strategy_id: str) -> Optional[CanaryMetrics]:
        """Get canary metrics for a strategy."""
        return self._canaries.get(strategy_id)

    async def list_canaries(self) -> list[CanaryMetrics]:
        """List all active canaries."""
        return list(self._canaries.values())
