"""
Canary release stage models.

Defines the data structures for canary
deployment stages, including percentage,
duration, health thresholds, and
promotion settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, Optional


@dataclass
class CanaryStage:
    """
    A single stage in a canary deployment.

    Each stage defines the traffic percentage,
    minimum duration, health check thresholds,
    and promotion behavior.

    Attributes:
        stage_id: Unique stage identifier.
        percentage: Traffic percentage for this stage.
        duration: Minimum stage duration before promotion.
        health_threshold: Health score threshold (0-100) to pass.
        error_rate_threshold: Max error rate percentage to allow.
        latency_p99_threshold_ms: Max P99 latency in milliseconds.
        auto_promote: Whether to auto-promote when health passes.
        description: Human-readable description.
    """

    stage_id: str = ""
    percentage: float = 0.0
    duration: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    health_threshold: float = 95.0
    error_rate_threshold: float = 5.0
    latency_p99_threshold_ms: float = 500.0
    auto_promote: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        """Validate stage after initialization."""
        if self.percentage < 0 or self.percentage > 100:
            raise ValueError(
                f"Stage percentage must be 0-100, got: {self.percentage}",
            )
        if self.health_threshold < 0 or self.health_threshold > 100:
            raise ValueError(
                f"Health threshold must be 0-100, got: {self.health_threshold}",
            )
        if self.error_rate_threshold < 0 or self.error_rate_threshold > 100:
            raise ValueError(
                f"Error rate threshold must be 0-100, got: {self.error_rate_threshold}",
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the stage to a dictionary."""
        return {
            "stage_id": self.stage_id,
            "percentage": self.percentage,
            "duration_seconds": self.duration.total_seconds(),
            "health_threshold": self.health_threshold,
            "error_rate_threshold": self.error_rate_threshold,
            "latency_p99_threshold_ms": self.latency_p99_threshold_ms,
            "auto_promote": self.auto_promote,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanaryStage":
        """Create a stage from a dictionary."""
        return cls(
            stage_id=data.get("stage_id", ""),
            percentage=data.get("percentage", 0.0),
            duration=timedelta(seconds=data.get("duration_seconds", 300)),
            health_threshold=data.get("health_threshold", 95.0),
            error_rate_threshold=data.get("error_rate_threshold", 5.0),
            latency_p99_threshold_ms=data.get("latency_p99_threshold_ms", 500.0),
            auto_promote=data.get("auto_promote", True),
            description=data.get("description", ""),
        )


# Default canary stages
DEFAULT_CANARY_STAGES = [
    CanaryStage(
        stage_id="canary-1",
        percentage=1.0,
        duration=timedelta(minutes=5),
        health_threshold=99.0,
        error_rate_threshold=1.0,
        latency_p99_threshold_ms=200.0,
        auto_promote=True,
        description="Initial canary (1%)",
    ),
    CanaryStage(
        stage_id="canary-2",
        percentage=5.0,
        duration=timedelta(minutes=10),
        health_threshold=98.0,
        error_rate_threshold=2.0,
        latency_p99_threshold_ms=300.0,
        auto_promote=True,
        description="Early canary (5%)",
    ),
    CanaryStage(
        stage_id="canary-3",
        percentage=25.0,
        duration=timedelta(minutes=15),
        health_threshold=97.0,
        error_rate_threshold=3.0,
        latency_p99_threshold_ms=400.0,
        auto_promote=True,
        description="Mid canary (25%)",
    ),
    CanaryStage(
        stage_id="canary-4",
        percentage=50.0,
        duration=timedelta(minutes=15),
        health_threshold=96.0,
        error_rate_threshold=4.0,
        latency_p99_threshold_ms=450.0,
        auto_promote=True,
        description="Wide canary (50%)",
    ),
    CanaryStage(
        stage_id="canary-5",
        percentage=100.0,
        duration=timedelta(minutes=0),
        health_threshold=95.0,
        error_rate_threshold=5.0,
        latency_p99_threshold_ms=500.0,
        auto_promote=False,
        description="Full rollout (100%)",
    ),
]


@dataclass
class CanaryDeployment:
    """
    A canary deployment instance.

    Tracks the state of an active canary
    deployment across its stages.

    Attributes:
        deployment_id: Unique deployment identifier.
        feature_key: Feature flag key being deployed.
        stages: List of canary stages.
        current_stage_index: Current active stage.
        status: Deployment status.
        started_at: When the deployment started.
        completed_at: When the deployment completed.
    """

    deployment_id: str = ""
    feature_key: str = ""
    stages: list = field(default_factory=lambda: list(DEFAULT_CANARY_STAGES))
    current_stage_index: int = 0
    status: str = "pending"  # pending, running, completed, rolled_back, failed
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    @property
    def current_stage(self) -> CanaryStage:
        """Get the current active stage."""
        if 0 <= self.current_stage_index < len(self.stages):
            return self.stages[self.current_stage_index]
        return self.stages[-1] if self.stages else CanaryStage()

    @property
    def current_percentage(self) -> float:
        """Get the current traffic percentage."""
        return self.current_stage.percentage

    @property
    def is_complete(self) -> bool:
        """Check if deployment is at 100%."""
        return self.current_percentage >= 100.0

    @property
    def progress(self) -> float:
        """Get deployment progress as a fraction (0.0 to 1.0)."""
        if len(self.stages) <= 1:
            return 1.0
        return self.current_stage_index / (len(self.stages) - 1)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the deployment to a dictionary."""
        return {
            "deployment_id": self.deployment_id,
            "feature_key": self.feature_key,
            "stages": [s.to_dict() for s in self.stages],
            "current_stage_index": self.current_stage_index,
            "current_percentage": self.current_percentage,
            "status": self.status,
            "progress": self.progress,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }
