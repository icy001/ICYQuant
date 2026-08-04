"""
Canary release policy configuration.

Defines deployment policies with different
aggressiveness levels for canary rollouts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class CanaryPolicy:
    """
    Configuration for canary deployment behavior.

    Controls how aggressively the canary
    progresses through stages, when to
    auto-rollback, and health thresholds.

    Attributes:
        auto_promote: Whether to auto-promote on health pass.
        rollback_on_failure: Whether to auto-rollback on failure.
        rollback_threshold: Error rate threshold to trigger rollback (0-100).
        max_stage_duration_seconds: Max time in a stage before timeout.
        min_sample_size: Minimum requests before evaluating health.
        health_check_interval_seconds: How often to check health.
        strategy: Policy strategy (conservative, balanced, aggressive).
        notification_enabled: Whether to send notifications.
    """

    auto_promote: bool = True
    rollback_on_failure: bool = True
    rollback_threshold: float = 5.0
    max_stage_duration_seconds: float = 3600.0
    min_sample_size: int = 100
    health_check_interval_seconds: float = 30.0
    strategy: str = "balanced"
    notification_enabled: bool = True

    def __post_init__(self) -> None:
        """Validate policy after initialization."""
        valid_strategies = ("conservative", "balanced", "aggressive")
        if self.strategy not in valid_strategies:
            raise ValueError(
                f"Invalid strategy: {self.strategy}. "
                f"Valid: {', '.join(valid_strategies)}",
            )
        if self.rollback_threshold < 0 or self.rollback_threshold > 100:
            raise ValueError(
                f"Rollback threshold must be 0-100, got: {self.rollback_threshold}",
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the policy to a dictionary."""
        return {
            "auto_promote": self.auto_promote,
            "rollback_on_failure": self.rollback_on_failure,
            "rollback_threshold": self.rollback_threshold,
            "max_stage_duration_seconds": self.max_stage_duration_seconds,
            "min_sample_size": self.min_sample_size,
            "health_check_interval_seconds": self.health_check_interval_seconds,
            "strategy": self.strategy,
            "notification_enabled": self.notification_enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanaryPolicy":
        """Create a policy from a dictionary."""
        return cls(
            auto_promote=data.get("auto_promote", True),
            rollback_on_failure=data.get("rollback_on_failure", True),
            rollback_threshold=data.get("rollback_threshold", 5.0),
            max_stage_duration_seconds=data.get("max_stage_duration_seconds", 3600.0),
            min_sample_size=data.get("min_sample_size", 100),
            health_check_interval_seconds=data.get("health_check_interval_seconds", 30.0),
            strategy=data.get("strategy", "balanced"),
            notification_enabled=data.get("notification_enabled", True),
        )


# Pre-defined policy profiles
CONSERVATIVE_POLICY = CanaryPolicy(
    auto_promote=True,
    rollback_on_failure=True,
    rollback_threshold=2.0,
    max_stage_duration_seconds=7200.0,
    min_sample_size=500,
    health_check_interval_seconds=60.0,
    strategy="conservative",
)

BALANCED_POLICY = CanaryPolicy(
    auto_promote=True,
    rollback_on_failure=True,
    rollback_threshold=5.0,
    max_stage_duration_seconds=3600.0,
    min_sample_size=100,
    health_check_interval_seconds=30.0,
    strategy="balanced",
)

AGGRESSIVE_POLICY = CanaryPolicy(
    auto_promote=True,
    rollback_on_failure=True,
    rollback_threshold=10.0,
    max_stage_duration_seconds=900.0,
    min_sample_size=50,
    health_check_interval_seconds=15.0,
    strategy="aggressive",
)
