"""
Progressive rollout engine.

Manages multi-stage rollout plans that
gradually increase the percentage of
a feature flag over time. Supports:
    - Manual stage advancement
    - Automatic advancement with health checks
    - Scheduled advancement with delays
    - Error threshold blocking
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from .rollout import ProgressiveStage


class ProgressiveRollout:
    """
    Progressive rollout with multi-stage deployment.

    Manages the progression through a series of
    rollout stages, each with increasing percentage.
    Supports automatic advancement based on health
    metrics and manual control.

    Default stages follow a common pattern:
        5% → 10% → 25% → 50% → 100%

    Usage:
        rollout = ProgressiveRollout("new-risk-engine")
        rollout.add_stage(ProgressiveStage(percentage=5.0))
        rollout.add_stage(ProgressiveStage(percentage=10.0))
        rollout.start()
        current = rollout.current_percentage  # 5.0
        # After health check passes and min requests met
        rollout.advance()  # current becomes 10.0
    """

    DEFAULT_STAGES = [
        ProgressiveStage(stage_id="stage-1", percentage=5.0, min_requests=100, error_threshold=5.0),
        ProgressiveStage(stage_id="stage-2", percentage=10.0, min_requests=200, error_threshold=5.0),
        ProgressiveStage(stage_id="stage-3", percentage=25.0, min_requests=500, error_threshold=3.0),
        ProgressiveStage(stage_id="stage-4", percentage=50.0, min_requests=1000, error_threshold=2.0),
        ProgressiveStage(stage_id="stage-5", percentage=100.0, min_requests=2000, error_threshold=1.0),
    ]

    def __init__(
        self,
        feature_key: str,
        stages: Optional[List[ProgressiveStage]] = None,
    ) -> None:
        """
        Initialize the progressive rollout.

        Args:
            feature_key: Feature flag key.
            stages: Optional custom stages (defaults to standard progression).
        """
        self._feature_key = feature_key
        self._stages = stages or list(self.DEFAULT_STAGES)
        self._current_stage_index = 0
        self._is_active = False
        self._start_time: Optional[float] = None
        self._stage_enter_time: Optional[float] = None
        self._request_count = 0
        self._error_count = 0
        self._lock = asyncio.Lock()
        self._advancement_callbacks: List[Any] = []

    def start(self) -> None:
        """Start the progressive rollout."""
        self._is_active = True
        self._start_time = time.time()
        self._stage_enter_time = time.time()

    def stop(self) -> None:
        """Stop the progressive rollout."""
        self._is_active = False
        self._start_time = None
        self._stage_enter_time = None

    def advance(self, force: bool = False) -> bool:
        """
        Advance to the next stage.

        Args:
            force: Force advancement regardless of conditions.

        Returns:
            True if advanced successfully.
        """
        if not self._is_active:
            return False

        if self._current_stage_index >= len(self._stages) - 1:
            return False

        current = self._stages[self._current_stage_index]

        if not force and current.auto_advance:
            if not self._can_advance(current):
                return False

        self._current_stage_index += 1
        self._stage_enter_time = time.time()
        self._request_count = 0
        self._error_count = 0

        # Fire callbacks
        for callback in self._advancement_callbacks:
            try:
                callback(self._current_stage)
            except Exception:
                pass

        return True

    def rollback(self) -> bool:
        """
        Rollback to the previous stage.

        Returns:
            True if rolled back successfully.
        """
        if self._current_stage_index <= 0:
            return False

        self._current_stage_index -= 1
        self._stage_enter_time = time.time()
        self._request_count = 0
        self._error_count = 0
        return True

    def _can_advance(self, stage: ProgressiveStage) -> bool:
        """Check if conditions are met for advancement."""
        # Check minimum requests
        if self._request_count < stage.min_requests:
            return False

        # Check error threshold
        if self._request_count > 0:
            error_rate = (self._error_count / self._request_count) * 100
            if error_rate > stage.error_threshold:
                return False

        # Check delay
        if stage.delay_seconds > 0 and self._stage_enter_time:
            elapsed = time.time() - self._stage_enter_time
            if elapsed < stage.delay_seconds:
                return False

        return True

    def record_request(self, error: bool = False) -> None:
        """
        Record a request for the current stage.

        Args:
            error: Whether the request was an error.
        """
        self._request_count += 1
        if error:
            self._error_count += 1

    def add_stage(self, stage: ProgressiveStage) -> None:
        """Add a stage to the rollout plan."""
        self._stages.append(stage)
        self._stages.sort(key=lambda s: s.percentage)

    def on_advance(self, callback: Any) -> None:
        """Register a callback for stage advancement."""
        self._advancement_callbacks.append(callback)

    @property
    def current_percentage(self) -> float:
        """Get the current rollout percentage."""
        return self._current_stage.percentage if self._stages else 0.0

    @property
    def _current_stage(self) -> ProgressiveStage:
        """Get the current stage."""
        return self._stages[self._current_stage_index]

    @property
    def current_stage_index(self) -> int:
        """Get the current stage index."""
        return self._current_stage_index

    @property
    def is_active(self) -> bool:
        """Check if the rollout is active."""
        return self._is_active

    @property
    def total_stages(self) -> int:
        """Get total number of stages."""
        return len(self._stages)

    @property
    def progress(self) -> float:
        """Get rollout progress as a fraction (0.0 to 1.0)."""
        if len(self._stages) <= 1:
            return 1.0
        return self._current_stage_index / (len(self._stages) - 1)

    def get_current_stage(self) -> ProgressiveStage:
        """Get the current stage."""
        return self._current_stage

    def get_stage(self, index: int) -> Optional[ProgressiveStage]:
        """Get a stage by index."""
        if 0 <= index < len(self._stages):
            return self._stages[index]
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get progressive rollout statistics."""
        error_rate = (
            (self._error_count / self._request_count) * 100
            if self._request_count > 0
            else 0.0
        )
        elapsed = (
            time.time() - self._start_time
            if self._start_time
            else 0.0
        )
        return {
            "feature_key": self._feature_key,
            "active": self._is_active,
            "current_stage_index": self._current_stage_index,
            "current_percentage": self.current_percentage,
            "total_stages": len(self._stages),
            "progress": self.progress,
            "requests": self._request_count,
            "errors": self._error_count,
            "error_rate": error_rate,
            "elapsed_seconds": elapsed,
            "can_advance": self._can_advance(self._current_stage) if self._is_active else False,
        }

    def reset(self) -> None:
        """Reset the progressive rollout."""
        self._current_stage_index = 0
        self._is_active = False
        self._start_time = None
        self._stage_enter_time = None
        self._request_count = 0
        self._error_count = 0
