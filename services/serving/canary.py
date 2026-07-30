"""Canary Release — gradual model rollout with automatic rollback.

Safely releases new models by ramping traffic from 5%→10%→25%→50%→100%
with automatic rollback on anomaly detection.

Usage::

    canary = CanaryManager(config=CanaryConfig())
    canary.start_rollout("alpha_v38", model=None)
    canary.advance()  # move to next stage
    canary.rollback()  # instant rollback on anomaly
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class CanaryStage(str, Enum):
    """Canary rollout stages with predefined traffic shares."""
    INITIAL = "initial"    # 5%
    LOW = "low"            # 10%
    MEDIUM = "medium"      # 25%
    HIGH = "high"          # 50%
    FULL = "full"          # 100%


class RolloutState(str, Enum):
    """Current state of a canary rollout."""
    IDLE = "idle"
    ROLLING_OUT = "rolling_out"
    PAUSED = "paused"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


# Stage → traffic percentage
_STAGE_TRAFFIC: Dict[CanaryStage, float] = {
    CanaryStage.INITIAL: 0.05,
    CanaryStage.LOW: 0.10,
    CanaryStage.MEDIUM: 0.25,
    CanaryStage.HIGH: 0.50,
    CanaryStage.FULL: 1.00,
}

# Stage ordering for progression
_STAGE_ORDER: List[CanaryStage] = [
    CanaryStage.INITIAL,
    CanaryStage.LOW,
    CanaryStage.MEDIUM,
    CanaryStage.HIGH,
    CanaryStage.FULL,
]


@dataclass
class CanaryConfig:
    """Canary release configuration.

    Attributes:
        stages: Stages to use for rollout.
        min_duration_per_stage: Minimum seconds per stage before advance.
        max_duration_per_stage: Maximum seconds before auto-advance.
        anomaly_thresholds: Dict of metric → threshold for rollback.
        auto_advance: Whether to auto-advance stages.
        auto_rollback: Whether to auto-rollback on anomaly.
        health_check_interval: Seconds between health checks.
    """

    stages: List[CanaryStage] = field(default_factory=lambda: list(_STAGE_ORDER))
    min_duration_per_stage: float = 300.0   # 5 minutes
    max_duration_per_stage: float = 3600.0  # 1 hour
    anomaly_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "error_rate": 0.01,
        "latency_p99_ms": 100.0,
        "prediction_drift": 0.3,
    })
    auto_advance: bool = False
    auto_rollback: bool = True
    health_check_interval: float = 60.0


@dataclass
class CanaryStatus:
    """Current canary rollout status.

    Attributes:
        model_name: The new model being rolled out.
        current_stage: Current rollout stage.
        traffic_share: Current traffic percentage.
        state: Rollout state.
        started_at: Rollout start time.
        stage_started_at: Current stage start time.
        metrics: Current health/performance metrics.
    """

    model_name: str = ""
    current_stage: CanaryStage = CanaryStage.INITIAL
    traffic_share: float = 0.0
    state: RolloutState = RolloutState.IDLE
    started_at: Optional[float] = None
    stage_started_at: Optional[float] = None
    metrics: Dict[str, float] = field(default_factory=dict)


class CanaryManager:
    """Manages canary release with staged traffic rollout.

    Progressively increases traffic to a new model while monitoring
    for anomalies. Supports instant rollback to the previous stable model.

    Usage::

        canary = CanaryManager(config=CanaryConfig())
        canary.start_rollout("alpha_v38", new_model, current_model="alpha_v37")
        while canary.status.state == RolloutState.ROLLING_OUT:
            time.sleep(60)
            healthy = canary.health_check()
            if healthy:
                canary.advance()
            else:
                canary.rollback()
    """

    def __init__(self, config: Optional[CanaryConfig] = None):
        self.config = config or CanaryConfig()
        self.status = CanaryStatus()
        self._new_model: Any = None
        self._current_model: Any = None
        self._current_model_name: str = ""
        self._stage_index: int = 0
        self._metrics_history: List[Dict[str, Any]] = []
        self._health_callbacks: List[Callable] = []
        self._rollback_callbacks: List[Callable] = []

    def start_rollout(
        self,
        model_name: str,
        new_model: Any = None,
        current_model: Any = None,
        current_model_name: str = "",
    ) -> None:
        """Start a canary rollout for a new model.

        Args:
            model_name: New model identifier.
            new_model: The new model object.
            current_model: Currently serving model (for rollback).
            current_model_name: Current model name.
        """
        if not self.config.stages:
            raise ValueError("No stages configured")

        self._new_model = new_model
        self._current_model = current_model
        self._current_model_name = current_model_name
        self._stage_index = 0
        first_stage = self.config.stages[0]

        self.status = CanaryStatus(
            model_name=model_name,
            current_stage=first_stage,
            traffic_share=_STAGE_TRAFFIC.get(first_stage, 0.0),
            state=RolloutState.ROLLING_OUT,
            started_at=time.time(),
            stage_started_at=time.time(),
        )

    def advance(self) -> CanaryStatus:
        """Advance to the next rollout stage.

        Returns:
            Updated CanaryStatus.
        """
        if self.status.state != RolloutState.ROLLING_OUT:
            return self.status

        next_index = self._stage_index + 1
        if next_index >= len(self.config.stages):
            # Reached full rollout
            self.status.current_stage = CanaryStage.FULL
            self.status.traffic_share = 1.0
            self.status.state = RolloutState.COMPLETED
            self.status.stage_started_at = time.time()
            return self.status

        current_stage = self.config.stages[self._stage_index]
        stage_duration = time.time() - (self.status.stage_started_at or 0)

        if stage_duration < self.config.min_duration_per_stage:
            raise RuntimeError(
                f"Minimum stage duration not met: {stage_duration:.0f}s < "
                f"{self.config.min_duration_per_stage}s"
            )

        self._stage_index = next_index
        next_stage = self.config.stages[next_index]

        self.status.current_stage = next_stage
        self.status.traffic_share = _STAGE_TRAFFIC.get(next_stage, 0.0)
        self.status.stage_started_at = time.time()

        if next_stage == CanaryStage.FULL:
            self.status.state = RolloutState.COMPLETED

        return self.status

    def rollback(self) -> CanaryStatus:
        """Immediate rollback to previous stable model.

        Returns:
            Updated CanaryStatus.
        """
        self.status.state = RolloutState.ROLLED_BACK
        self.status.traffic_share = 0.0

        for cb in self._rollback_callbacks:
            try:
                cb(self._current_model_name or self.status.model_name)
            except Exception:
                pass

        return self.status

    def pause(self) -> None:
        """Pause the rollout at current stage."""
        if self.status.state == RolloutState.ROLLING_OUT:
            self.status.state = RolloutState.PAUSED

    def resume(self) -> None:
        """Resume a paused rollout."""
        if self.status.state == RolloutState.PAUSED:
            self.status.state = RolloutState.ROLLING_OUT

    def get_traffic_share(self) -> float:
        """Get current traffic share for the new model."""
        return self.status.traffic_share

    def is_new_model(self, hash_val: float) -> bool:
        """Check if a hashed request should go to the new model.

        Args:
            hash_val: Consistent hash value in [0, 1] for the request.

        Returns:
            True if the request should use the new model.
        """
        if self.status.state in (RolloutState.IDLE, RolloutState.ROLLED_BACK):
            return False
        if self.status.state == RolloutState.COMPLETED:
            return True
        return hash_val < self.status.traffic_share

    def health_check(self) -> bool:
        """Run health checks against anomaly thresholds.

        Returns:
            True if healthy, False if anomaly detected.
        """
        if not self.status.metrics:
            return True

        for metric, threshold in self.config.anomaly_thresholds.items():
            current = self.status.metrics.get(metric, 0.0)
            if current > threshold:
                if self.config.auto_rollback:
                    self.rollback()
                return False

        for cb in self._health_callbacks:
            try:
                if not cb(self.status.metrics):
                    return False
            except Exception:
                pass

        return True

    def update_metrics(self, metrics: Dict[str, float]) -> None:
        """Update health metrics for the current stage.

        Args:
            metrics: Metric name → value mapping.
        """
        self.status.metrics.update(metrics)
        self._metrics_history.append({
            "timestamp": time.time(),
            "stage": self.status.current_stage.value,
            **metrics,
        })

    def add_health_callback(self, callback: Callable[[Dict[str, float]], bool]) -> None:
        """Register a custom health check function."""
        self._health_callbacks.append(callback)

    def add_rollback_callback(self, callback: Callable[[str], None]) -> None:
        """Register a callback invoked on rollback."""
        self._rollback_callbacks.append(callback)

    def get_metrics_history(self) -> List[Dict[str, Any]]:
        """Get historical metrics for the current rollout."""
        return list(self._metrics_history)

    def reset(self) -> None:
        """Reset the canary manager to idle state."""
        self.status = CanaryStatus()
        self._stage_index = 0
        self._metrics_history.clear()
        self._new_model = None
