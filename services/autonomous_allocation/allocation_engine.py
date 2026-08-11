"""Autonomous Allocation Engine — central orchestration of the allocation pipeline.

Pipeline:
    Market Data → Strategy Signals → Alpha → Risk → Capacity → Liquidity
    → Impact → Stress → Survival → Allocation Score → Optimization
    → Constraint Check → Decision → Rebalance → Execution → Feedback
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class EngineMode(str, Enum):
    """Allocation engine operating mode."""
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    STRESS = "STRESS"
    DEFENSIVE = "DEFENSIVE"
    EMERGENCY = "EMERGENCY"


class EngineStatus(str, Enum):
    """Engine lifecycle status."""
    IDLE = "IDLE"
    COLLECTING = "COLLECTING"
    SCORING = "SCORING"
    OPTIMIZING = "OPTIMIZING"
    DECIDING = "DECIDING"
    REBALANCING = "REBALANCING"
    EXECUTING = "EXECUTING"
    FEEDBACK = "FEEDBACK"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


@dataclass
class AllocationContext:
    """Context passed through the allocation pipeline."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_capital: float = 0.0
    mode: EngineMode = EngineMode.NORMAL
    strategy_ids: List[str] = field(default_factory=list)
    market_state: Dict[str, Any] = field(default_factory=dict)
    risk_budget: float = 0.0
    constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AllocationPipelineResult:
    """Complete allocation pipeline result."""
    context: AllocationContext
    scores: Dict[str, Dict[str, float]] = field(default_factory=dict)
    marginal_analysis: Dict[str, Dict[str, float]] = field(default_factory=dict)
    rankings: List[Tuple[str, float]] = field(default_factory=list)
    target_weights: Dict[str, float] = field(default_factory=dict)
    decisions: Dict[str, str] = field(default_factory=dict)
    rebalance_plan: Dict[str, Any] = field(default_factory=dict)
    constraint_violations: List[str] = field(default_factory=list)
    guard_result: str = "PENDING"
    status: EngineStatus = EngineStatus.IDLE
    errors: List[str] = field(default_factory=list)
    trace_id: str = ""


class AllocationEngine:
    """Central engine orchestrating the full autonomous allocation pipeline.

    Integrates: scoring, marginal analysis, optimization, constraints,
    decision-making, rebalancing, and feedback into one execution loop.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._status = EngineStatus.IDLE
        self._mode = EngineMode.NORMAL
        self._pipeline_steps: List[Callable] = []
        self._observers: List[Callable] = []
        self._last_result: Optional[AllocationPipelineResult] = None
        self._paused = False
        self._trace_counter = 0

    @property
    def status(self) -> EngineStatus:
        return self._status

    @property
    def mode(self) -> EngineMode:
        return self._mode

    @property
    def last_result(self) -> Optional[AllocationPipelineResult]:
        return self._last_result

    def register_step(self, step: Callable) -> None:
        """Register a pipeline step callable."""
        self._pipeline_steps.append(step)

    def register_observer(self, observer: Callable) -> None:
        """Register an observer for pipeline events."""
        self._observers.append(observer)

    def set_mode(self, mode: EngineMode) -> None:
        """Set engine operating mode with safety checks."""
        valid_transitions = {
            EngineMode.NORMAL: {EngineMode.NORMAL, EngineMode.CAUTION, EngineMode.STRESS,
                                EngineMode.DEFENSIVE, EngineMode.EMERGENCY},
            EngineMode.CAUTION: {EngineMode.NORMAL, EngineMode.CAUTION, EngineMode.STRESS,
                                 EngineMode.DEFENSIVE, EngineMode.EMERGENCY},
            EngineMode.STRESS: {EngineMode.CAUTION, EngineMode.STRESS, EngineMode.DEFENSIVE,
                                EngineMode.EMERGENCY},
            EngineMode.DEFENSIVE: {EngineMode.CAUTION, EngineMode.STRESS, EngineMode.DEFENSIVE,
                                   EngineMode.EMERGENCY},
            EngineMode.EMERGENCY: {EngineMode.CAUTION, EngineMode.STRESS, EngineMode.DEFENSIVE,
                                   EngineMode.EMERGENCY},
        }
        if mode in valid_transitions.get(self._mode, set()):
            self._mode = mode
        else:
            raise ValueError(f"Invalid mode transition: {self._mode} → {mode}")

    def pause(self) -> None:
        """Pause the engine — only allowed from NORMAL or CAUTION."""
        if self._mode in (EngineMode.NORMAL, EngineMode.CAUTION):
            self._paused = True
            self._status = EngineStatus.PAUSED

    def resume(self) -> None:
        """Resume the engine."""
        self._paused = False
        self._status = EngineStatus.IDLE

    def run(self, context: AllocationContext) -> AllocationPipelineResult:
        """Execute the full allocation pipeline."""
        if self._paused:
            return AllocationPipelineResult(
                context=context,
                status=EngineStatus.PAUSED,
                errors=["Engine is paused"],
                trace_id=self._generate_trace_id(),
            )

        result = AllocationPipelineResult(
            context=context,
            trace_id=self._generate_trace_id(),
        )

        try:
            self._status = EngineStatus.COLLECTING
            self._notify_observers("pipeline_start", result)

            self._status = EngineStatus.SCORING
            result = self._run_scoring(result)
            self._notify_observers("scoring_complete", result)

            self._status = EngineStatus.OPTIMIZING
            result = self._run_optimization(result)
            self._notify_observers("optimization_complete", result)

            self._status = EngineStatus.DECIDING
            result = self._run_decision(result)
            self._notify_observers("decision_complete", result)

            self._status = EngineStatus.REBALANCING
            result = self._run_rebalance(result)
            self._notify_observers("rebalance_complete", result)

            self._status = EngineStatus.FEEDBACK
            result = self._run_feedback(result)
            self._notify_observers("feedback_complete", result)

            self._status = EngineStatus.IDLE
            self._last_result = result

        except Exception as e:
            result.status = EngineStatus.ERROR
            result.errors.append(str(e))
            self._status = EngineStatus.ERROR
            self._notify_observers("pipeline_error", result)

        return result

    def _run_scoring(self, result: AllocationPipelineResult) -> AllocationPipelineResult:
        """Run the scoring stage — to be injected with actual scorers."""
        for step in self._pipeline_steps:
            if hasattr(step, '__name__') and 'score' in step.__name__:
                try:
                    step(result)
                except Exception as e:
                    result.errors.append(f"Scoring error: {e}")
        return result

    def _run_optimization(self, result: AllocationPipelineResult) -> AllocationPipelineResult:
        """Run the optimization stage."""
        for step in self._pipeline_steps:
            if hasattr(step, '__name__') and 'optimiz' in step.__name__:
                try:
                    step(result)
                except Exception as e:
                    result.errors.append(f"Optimization error: {e}")
        return result

    def _run_decision(self, result: AllocationPipelineResult) -> AllocationPipelineResult:
        """Run the decision stage with guard checks."""
        for step in self._pipeline_steps:
            if hasattr(step, '__name__') and ('decision' in step.__name__ or 'guard' in step.__name__):
                try:
                    step(result)
                except Exception as e:
                    result.errors.append(f"Decision error: {e}")
        return result

    def _run_rebalance(self, result: AllocationPipelineResult) -> AllocationPipelineResult:
        """Run the rebalance stage."""
        for step in self._pipeline_steps:
            if hasattr(step, '__name__') and 'rebalance' in step.__name__:
                try:
                    step(result)
                except Exception as e:
                    result.errors.append(f"Rebalance error: {e}")
        return result

    def _run_feedback(self, result: AllocationPipelineResult) -> AllocationPipelineResult:
        """Run the feedback stage."""
        for step in self._pipeline_steps:
            if hasattr(step, '__name__') and 'feedback' in step.__name__:
                try:
                    step(result)
                except Exception as e:
                    result.errors.append(f"Feedback error: {e}")
        return result

    def _notify_observers(self, event: str, result: AllocationPipelineResult) -> None:
        """Notify all registered observers of pipeline events."""
        for observer in self._observers:
            try:
                observer(event, result)
            except Exception:
                pass

    def _generate_trace_id(self) -> str:
        """Generate a unique trace ID for this pipeline run."""
        self._trace_counter += 1
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        return f"alloc-{ts}-{self._trace_counter:06d}"

    def compute_allocation_utility(self, alpha: float, risk_penalty: float,
                                   txn_cost: float, impact: float,
                                   liquidity_penalty: float, stress_penalty: float,
                                   capacity_penalty: float) -> float:
        """Compute the unified allocation utility.

        Utility = Alpha - Risk - Cost - Impact - Liquidity - Stress - Capacity
        """
        return alpha - risk_penalty - txn_cost - impact - liquidity_penalty - stress_penalty - capacity_penalty

    def is_survival_compliant(self, survival_score: float, threshold: float) -> bool:
        """Check if the survival score meets minimum threshold."""
        return survival_score >= threshold
