"""Autonomous Capital Allocation Engine - Commit 19 Part 1.5.

ICYQuant v0.4.0-alpha2: Autonomous, risk-aware, capacity-constrained
capital allocation with closed-loop feedback.

Architecture:
    Alpha + Risk + Capacity + Liquidity + Impact + Stress + Survival
        → Allocation Score
        → Marginal Analysis
        → Optimization
        → Constraint Check
        → Allocation Decision
        → Rebalance Plan
        → Execution
        → Feedback Loop
"""

__all__ = [
    # Core Engine
    "AllocationEngine",
    "AllocationRuntime",
    "AllocationManager",
    "AllocationController",
    "AllocationOrchestrator",
    # Decision & State
    "AllocationDecision",
    "AllocationRequest",
    "AllocationResult",
    "AllocationState",
    "AllocationAction",
    "AutonomyLevel",
    # Capital Allocation Models
    "CapitalAllocator",
    "CapitalAllocationModel",
    "CapitalAllocationOptimizer",
    "CapitalAllocationSolver",
    # Scoring
    "AlphaScorer",
    "RiskScorer",
    "CapacityScorer",
    "LiquidityScorer",
    "ImpactScorer",
    "StressScorer",
    "SurvivalScorer",
    # Marginal Analysis
    "MarginalAlpha",
    "MarginalRisk",
    "MarginalCapacity",
    "MarginalCost",
    "MarginalSurvival",
    # Constraints
    "AllocationConstraint",
    "CapitalConstraint",
    "RiskConstraint",
    "CapacityConstraint",
    "LiquidityConstraint",
    "ConcentrationConstraint",
    "StressConstraint",
    "SurvivalConstraint",
    # Rebalance
    "RebalanceEngine",
    "RebalancePlanner",
    "RebalancePriority",
    "RebalanceThreshold",
    "RebalanceScheduler",
    # Capital Flow
    "CapitalInflow",
    "CapitalOutflow",
    "CapitalReserve",
    "CapitalBuffer",
    # Strategy Management
    "StrategyRanker",
    "StrategySelector",
    "StrategyWeight",
    "StrategyRotation",
    # Feedback & Learning
    "AllocationFeedback",
    "AllocationLearning",
    "AllocationMemory",
    "AllocationHistory",
    # Guards
    "DecisionGuard",
    "AllocationGuard",
    "AutonomyGuard",
    # Observability
    "AllocationMetrics",
    "AllocationTelemetry",
    "AllocationDiagnostics",
    "AllocationHealth",
]

from .allocation_engine import AllocationEngine
from .allocation_runtime import AllocationRuntime
from .allocation_manager import AllocationManager
from .allocation_controller import AllocationController
from .allocation_orchestrator import AllocationOrchestrator
from .allocation_decision import AllocationDecision
from .allocation_request import AllocationRequest
from .allocation_result import AllocationResult
from .allocation_state import AllocationState
from .allocation_action import AllocationAction, AutonomyLevel
from .capital_allocator import CapitalAllocator
from .capital_allocation_model import CapitalAllocationModel
from .capital_allocation_optimizer import CapitalAllocationOptimizer
from .capital_allocation_solver import CapitalAllocationSolver
from .alpha_score import AlphaScorer
from .risk_score import RiskScorer
from .capacity_score import CapacityScorer
from .liquidity_score import LiquidityScorer
from .impact_score import ImpactScorer
from .stress_score import StressScorer
from .survival_score import SurvivalScorer
from .marginal_alpha import MarginalAlpha
from .marginal_risk import MarginalRisk
from .marginal_capacity import MarginalCapacity
from .marginal_cost import MarginalCost
from .marginal_survival import MarginalSurvival
from .allocation_constraint import AllocationConstraint
from .capital_constraint import CapitalConstraint
from .risk_constraint import RiskConstraint
from .capacity_constraint import CapacityConstraint
from .liquidity_constraint import LiquidityConstraint
from .concentration_constraint import ConcentrationConstraint
from .stress_constraint import StressConstraint
from .survival_constraint import SurvivalConstraint
from .rebalance_engine import RebalanceEngine
from .rebalance_planner import RebalancePlanner
from .rebalance_priority import RebalancePriority
from .rebalance_threshold import RebalanceThreshold
from .rebalance_scheduler import RebalanceScheduler
from .capital_inflow import CapitalInflow
from .capital_outflow import CapitalOutflow
from .capital_reserve import CapitalReserve
from .capital_buffer import CapitalBuffer
from .strategy_ranker import StrategyRanker
from .strategy_selector import StrategySelector
from .strategy_weight import StrategyWeight
from .strategy_rotation import StrategyRotation
from .allocation_feedback import AllocationFeedback
from .allocation_learning import AllocationLearning
from .allocation_memory import AllocationMemory
from .allocation_history import AllocationHistory
from .decision_guard import DecisionGuard
from .allocation_guard import AllocationGuard
from .autonomy_guard import AutonomyGuard
from .metrics import AllocationMetrics
from .telemetry import AllocationTelemetry
from .diagnostics import AllocationDiagnostics
from .health import AllocationHealth
