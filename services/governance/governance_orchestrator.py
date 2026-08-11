"""
Governance Orchestrator — integrates governance into the full decision chain.

This sits between Autonomous Allocation and Execution, ensuring every
significant decision passes through governance before execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

from .governance_engine import GovernanceEngine, GovernanceEvaluation, GovernanceVerdict
from .governance_manager import GovernanceManager, GovernanceManagerConfig
from .decision_context import DecisionContext
from .decision_request import DecisionRequest, DecisionType
from .decision_result import DecisionResult, DecisionOutcome


class OrchestrationPhase(Enum):
    """Phases in the orchestrated decision chain."""

    PRE_FLIGHT = auto()       # Initial checks
    GOVERNANCE = auto()       # Governance evaluation
    POST_GOVERNANCE = auto()  # Post-governance adjustments
    EXECUTION = auto()        # Ready for execution
    CANCELLED = auto()        # Cancelled
    ERROR = auto()            # Error state


@dataclass
class OrchestrationResult:
    """Result of an orchestrated decision flow."""

    phase: OrchestrationPhase
    request_id: str
    decision_result: Optional[DecisionResult] = None
    governance_evaluation: Optional[GovernanceEvaluation] = None
    downstream_instruction: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)

    @property
    def is_allowed(self) -> bool:
        if self.decision_result:
            return self.decision_result.is_allowed
        return False

    @property
    def can_execute(self) -> bool:
        return self.phase == OrchestrationPhase.EXECUTION and self.is_allowed


@dataclass
class OrchestratorConfig:
    """Orchestrator configuration."""

    governance_manager: Optional[GovernanceManager] = None
    pre_flight_hooks: List[Callable[[DecisionRequest, DecisionContext], bool]] = field(default_factory=list)
    post_governance_hooks: List[Callable[[OrchestrationResult], OrchestrationResult]] = field(default_factory=list)
    strict_mode: bool = False
    allow_bypass: bool = False


class GovernanceOrchestrator:
    """
    Orchestrates the full decision flow:
        Pre-flight → Governance → Post-governance → Execution signal
    """

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self._config = config or OrchestratorConfig()
        self._manager = self._config.governance_manager or GovernanceManager(
            GovernanceManagerConfig()
        )
        self._manager.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def manager(self) -> GovernanceManager:
        return self._manager

    def process(self, request: DecisionRequest, context: DecisionContext) -> OrchestrationResult:
        """Run the full orchestrated decision flow."""
        result = OrchestrationResult(
            phase=OrchestrationPhase.PRE_FLIGHT,
            request_id=request.request_id,
        )

        # Phase 1: Pre-flight
        for hook in self._config.pre_flight_hooks:
            try:
                if not hook(request, context):
                    result.phase = OrchestrationPhase.CANCELLED
                    result.errors.append("Pre-flight hook rejected")
                    return result
            except Exception as exc:
                if self._config.strict_mode:
                    result.phase = OrchestrationPhase.ERROR
                    result.errors.append(f"Pre-flight hook error: {exc}")
                    return result

        # Phase 2: Governance
        result.phase = OrchestrationPhase.GOVERNANCE
        decision_result = self._manager.evaluate(request, context)
        result.decision_result = decision_result

        if not decision_result.is_allowed:
            result.phase = OrchestrationPhase.CANCELLED
            return result

        # Phase 3: Post-governance
        result.phase = OrchestrationPhase.POST_GOVERNANCE
        for hook in self._config.post_governance_hooks:
            try:
                result = hook(result)
            except Exception as exc:
                if self._config.strict_mode:
                    result.phase = OrchestrationPhase.ERROR
                    result.errors.append(f"Post-governance hook error: {exc}")
                    return result

        # Phase 4: Ready for execution
        result.phase = OrchestrationPhase.EXECUTION
        return result

    def quick_check(self, request: DecisionRequest, context: DecisionContext) -> bool:
        """Simple allow/deny without full orchestration."""
        return self._manager.is_allowed(request, context)

    # ------------------------------------------------------------------
    # Convenience builders
    # ------------------------------------------------------------------

    @staticmethod
    def build_allocation_request(
        actor: str,
        strategy_id: str,
        current_allocation: float,
        target_allocation: float,
        capital_pool: float,
        request_id: Optional[str] = None,
    ) -> DecisionRequest:
        """Build a standard capital allocation decision request."""
        return DecisionRequest(
            request_id=request_id,
            actor=actor,
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            strategy_id=strategy_id,
            requested_amount=target_allocation - current_allocation,
            metadata={
                "current_allocation": current_allocation,
                "target_allocation": target_allocation,
                "capital_pool": capital_pool,
            },
        )

    @staticmethod
    def build_allocation_context(
        capital: float = 100_000_000,
        risk_budget_total: float = 8_000_000,
        risk_budget_used: float = 5_000_000,
        survival_score: float = 82.0,
        liquidity_score: float = 75.0,
        stress_survival: float = 70.0,
        **kwargs,
    ) -> DecisionContext:
        """Build a standard decision context for allocation decisions."""
        return DecisionContext(
            capital=capital,
            risk_budget_total=risk_budget_total,
            risk_budget_used=risk_budget_used,
            survival_score=survival_score,
            liquidity_score=liquidity_score,
            stress_survival_score=stress_survival,
            **kwargs,
        )

    def stop(self) -> None:
        self._manager.stop()
