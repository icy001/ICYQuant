"""
ICYQuant Deployment Strategy — Defines and executes deployment rollout strategies.

Strategies supported:
  - Blue/Green: Instant switch between two environments
  - Canary: Progressive traffic shifting with monitoring gates
  - Shadow: Mirror production traffic for evaluation
  - A/B: Side-by-side comparison with controlled traffic split
  - Rolling: Gradual instance replacement
  - All-at-once: Direct production replacement

Each strategy defines:
  - State transition sequence
  - Validation gates between stages
  - Rollback triggers
  - Traffic allocation rules
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StrategyType(str, Enum):
    """Deployment strategy types."""
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    SHADOW = "shadow"
    AB_TEST = "ab_test"
    ROLLING = "rolling"
    ALL_AT_ONCE = "all_at_once"


class StrategyPhase(str, Enum):
    """Phases within a deployment strategy."""
    PREPARING = "preparing"
    DEPLOYING = "deploying"
    VALIDATING = "validating"
    SHIFTING_TRAFFIC = "shifting_traffic"
    STABILIZING = "stabilizing"
    COMPLETED = "completed"
    ROLLING_BACK = "rolling_back"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TrafficStep:
    """A single traffic shift step."""
    target_percent: float
    duration_seconds: float
    validate: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_percent": self.target_percent,
            "duration_seconds": self.duration_seconds,
            "validate": self.validate,
        }


@dataclass
class ValidationGate:
    """Condition that must pass before proceeding to next phase."""
    name: str
    check_fn: Optional[Callable[[], bool]] = None
    min_duration_seconds: float = 0.0
    max_error_rate: float = 0.05
    max_latency_ms: float = 1000.0
    min_throughput: float = 0.0

    async def evaluate(self, metrics: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """Evaluate whether this gate passes.

        Returns:
            (passed, reason) tuple.
        """
        if self.check_fn:
            try:
                passed = self.check_fn()
                return passed, "custom_check" if passed else "custom_check_failed"
            except Exception as exc:
                return False, f"check_error: {exc}"

        if metrics is None:
            return True, "no_metrics"

        # Evaluate thresholds
        error_rate = metrics.get("error_rate", 0.0)
        if error_rate > self.max_error_rate:
            return False, f"error_rate {error_rate} > {self.max_error_rate}"

        latency_ms = metrics.get("p99_latency_ms", 0.0)
        if latency_ms > self.max_latency_ms:
            return False, f"latency {latency_ms}ms > {self.max_latency_ms}ms"

        return True, "all_gates_passed"


@dataclass
class StrategyConfig:
    """Configuration for a deployment strategy."""
    strategy_type: StrategyType = StrategyType.CANARY
    traffic_steps: List[TrafficStep] = field(default_factory=lambda: [
        TrafficStep(target_percent=5.0, duration_seconds=600),   # 10 min
        TrafficStep(target_percent=10.0, duration_seconds=600),
        TrafficStep(target_percent=25.0, duration_seconds=900),  # 15 min
        TrafficStep(target_percent=50.0, duration_seconds=1800),  # 30 min
        TrafficStep(target_percent=75.0, duration_seconds=1800),
        TrafficStep(target_percent=100.0, duration_seconds=3600),  # 1 hour
    ])
    validation_gates: List[ValidationGate] = field(default_factory=list)
    auto_promote: bool = False
    auto_rollback: bool = True
    rollback_on_error: bool = True
    warmup_seconds: float = 30.0
    cooldown_seconds: float = 60.0
    max_deployment_seconds: float = 86400.0  # 24 hours
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_type": self.strategy_type.value,
            "traffic_steps": [s.to_dict() for s in self.traffic_steps],
            "validation_gates": len(self.validation_gates),
            "auto_promote": self.auto_promote,
            "auto_rollback": self.auto_rollback,
        }


@dataclass
class StrategyExecution:
    """Runtime state of a strategy execution."""
    execution_id: str
    model_id: str
    candidate_version: str
    strategy: StrategyConfig
    current_phase: StrategyPhase = StrategyPhase.PREPARING
    current_step_index: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    phase_started_at: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    metrics_history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def record_metrics(self, metrics: Dict[str, Any]) -> None:
        self.metrics_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": self.current_phase.value,
            "step": self.current_step_index,
            "metrics": metrics,
        })

    def record_error(self, error: str) -> None:
        self.errors.append(f"[{self.current_phase.value}] {error}")

    def get_current_traffic_percent(self) -> float:
        if self.current_step_index < len(self.strategy.traffic_steps):
            return self.strategy.traffic_steps[self.current_step_index].target_percent
        return 100.0

    def is_terminal(self) -> bool:
        return self.current_phase in (
            StrategyPhase.COMPLETED,
            StrategyPhase.FAILED,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "model_id": self.model_id,
            "candidate_version": self.candidate_version,
            "strategy_type": self.strategy.strategy_type.value,
            "current_phase": self.current_phase.value,
            "current_step": self.current_step_index,
            "traffic_percent": self.get_current_traffic_percent(),
            "started_at": self.started_at,
            "errors_count": len(self.errors),
        }


# ---------------------------------------------------------------------------
# Strategy Registry
# ---------------------------------------------------------------------------

class DeploymentStrategyRegistry:
    """Registry of deployment strategies."""

    _strategies: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a strategy class."""
        def decorator(strategy_cls: type):
            cls._strategies[name] = strategy_cls
            return strategy_cls
        return decorator

    @classmethod
    def get(cls, name: str) -> Optional[type]:
        return cls._strategies.get(name)

    @classmethod
    def list_strategies(cls) -> List[str]:
        return list(cls._strategies.keys())


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------

class BaseDeploymentStrategy(ABC):
    """Abstract base for deployment strategies."""

    strategy_type: StrategyType

    @abstractmethod
    def get_config(self) -> StrategyConfig:
        """Return default config for this strategy."""
        ...

    @abstractmethod
    async def validate(self, execution: StrategyExecution) -> Tuple[bool, str]:
        """Validate deployment readiness.

        Returns:
            (ready, message) tuple.
        """
        ...

    @abstractmethod
    async def should_promote(
        self,
        execution: StrategyExecution,
        metrics: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Determine if candidate should be promoted.

        Returns:
            (promote, reason) tuple.
        """
        ...


@DeploymentStrategyRegistry.register("canary")
class CanaryStrategy(BaseDeploymentStrategy):
    """Canary deployment — progressive traffic shifting.

    Typical flow:
      5% → validate → 10% → validate → 25% → validate → 50% → ... → 100%
    """

    strategy_type = StrategyType.CANARY

    def get_config(self) -> StrategyConfig:
        return StrategyConfig(
            strategy_type=StrategyType.CANARY,
            validation_gates=[
                ValidationGate(
                    name="error_rate_gate",
                    max_error_rate=0.02,
                ),
                ValidationGate(
                    name="latency_gate",
                    max_latency_ms=500.0,
                ),
            ],
            auto_promote=False,
            auto_rollback=True,
        )

    async def validate(self, execution: StrategyExecution) -> Tuple[bool, str]:
        """Check if canary conditions are met."""
        if not execution.metrics_history:
            return True, "no_history_yet"

        latest = execution.metrics_history[-1]
        metrics = latest.get("metrics", {})

        error_rate = metrics.get("error_rate", 0.0)
        if error_rate > 0.05:
            return False, f"error_rate_too_high: {error_rate}"

        return True, "canary_healthy"

    async def should_promote(
        self,
        execution: StrategyExecution,
        metrics: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Promote if all steps completed and metrics are stable."""
        total_steps = len(execution.strategy.traffic_steps)
        if execution.current_step_index < total_steps - 1:
            return False, "canary_not_complete"

        # Check final metrics
        error_rate = metrics.get("error_rate", 0.0)
        if error_rate > 0.02:
            return False, f"final_error_rate: {error_rate}"

        latency = metrics.get("p99_latency_ms", 0.0)
        if latency > 1000.0:
            return False, f"high_latency: {latency}ms"

        return True, "canary_passed"


@DeploymentStrategyRegistry.register("blue_green")
class BlueGreenStrategy(BaseDeploymentStrategy):
    """Blue/Green deployment — instant environment switch.

    Two identical environments. Deploy to inactive (green),
    route traffic switch, keep blue for rollback.
    """

    strategy_type = StrategyType.BLUE_GREEN

    def get_config(self) -> StrategyConfig:
        return StrategyConfig(
            strategy_type=StrategyType.BLUE_GREEN,
            traffic_steps=[
                TrafficStep(target_percent=100.0, duration_seconds=0, validate=True),
            ],
            warmup_seconds=60.0,
            cooldown_seconds=300.0,
        )

    async def validate(self, execution: StrategyExecution) -> Tuple[bool, str]:
        return True, "ready"

    async def should_promote(
        self,
        execution: StrategyExecution,
        metrics: Dict[str, Any],
    ) -> Tuple[bool, str]:
        error_rate = metrics.get("error_rate", 0.0)
        if error_rate > 0.01:
            return False, f"error_rate: {error_rate}"
        return True, "green_validated"


@DeploymentStrategyRegistry.register("shadow")
class ShadowStrategy(BaseDeploymentStrategy):
    """Shadow deployment — mirror traffic without affecting production.

    Candidate receives same inputs, predictions logged but not used.
    Used for safe evaluation of new model versions.
    """

    strategy_type = StrategyType.SHADOW

    def get_config(self) -> StrategyConfig:
        return StrategyConfig(
            strategy_type=StrategyType.SHADOW,
            traffic_steps=[
                TrafficStep(target_percent=0.0, duration_seconds=0, validate=False),
            ],
            auto_promote=False,
            auto_rollback=False,
        )

    async def validate(self, execution: StrategyExecution) -> Tuple[bool, str]:
        # Shadow always passes — it's risk-free
        return True, "shadow_active"

    async def should_promote(
        self,
        execution: StrategyExecution,
        metrics: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Promote shadow to canary if metrics are better than production."""
        candidate_ic = metrics.get("candidate_ic", None)
        production_ic = metrics.get("production_ic", None)

        if candidate_ic is not None and production_ic is not None:
            if candidate_ic > production_ic:
                return True, f"Shadow IC ({candidate_ic:.4f}) > Production ({production_ic:.4f})"

        return False, "shadow_evaluating"


@DeploymentStrategyRegistry.register("all_at_once")
class AllAtOnceStrategy(BaseDeploymentStrategy):
    """Direct production replacement — immediate switch."""

    strategy_type = StrategyType.ALL_AT_ONCE

    def get_config(self) -> StrategyConfig:
        return StrategyConfig(
            strategy_type=StrategyType.ALL_AT_ONCE,
            traffic_steps=[
                TrafficStep(target_percent=100.0, duration_seconds=0),
            ],
            auto_rollback=True,
        )

    async def validate(self, execution: StrategyExecution) -> Tuple[bool, str]:
        return True, "ready"

    async def should_promote(
        self,
        execution: StrategyExecution,
        metrics: Dict[str, Any],
    ) -> Tuple[bool, str]:
        return True, "deployed"


@DeploymentStrategyRegistry.register("rolling")
class RollingStrategy(BaseDeploymentStrategy):
    """Rolling deployment — gradual instance replacement."""

    strategy_type = StrategyType.ROLLING

    def get_config(self) -> StrategyConfig:
        return StrategyConfig(
            strategy_type=StrategyType.ROLLING,
            traffic_steps=[
                TrafficStep(target_percent=25.0, duration_seconds=300),
                TrafficStep(target_percent=50.0, duration_seconds=300),
                TrafficStep(target_percent=75.0, duration_seconds=300),
                TrafficStep(target_percent=100.0, duration_seconds=600),
            ],
        )

    async def validate(self, execution: StrategyExecution) -> Tuple[bool, str]:
        return True, "ready"

    async def should_promote(
        self,
        execution: StrategyExecution,
        metrics: Dict[str, Any],
    ) -> Tuple[bool, str]:
        if execution.current_step_index >= len(execution.strategy.traffic_steps) - 1:
            return True, "rollout_complete"
        return False, "rolling_in_progress"


# ---------------------------------------------------------------------------
# Strategy factory
# ---------------------------------------------------------------------------

def create_strategy(strategy_type: StrategyType) -> BaseDeploymentStrategy:
    """Factory to create a deployment strategy instance."""
    strategy_map: Dict[StrategyType, BaseDeploymentStrategy] = {
        StrategyType.CANARY: CanaryStrategy(),
        StrategyType.BLUE_GREEN: BlueGreenStrategy(),
        StrategyType.SHADOW: ShadowStrategy(),
        StrategyType.ALL_AT_ONCE: AllAtOnceStrategy(),
        StrategyType.ROLLING: RollingStrategy(),
        StrategyType.AB_TEST: CanaryStrategy(),  # A/B uses canary pattern
    }

    strategy = strategy_map.get(strategy_type)
    if strategy is None:
        raise ValueError(f"Unknown strategy type: {strategy_type}")

    return strategy
