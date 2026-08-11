"""
Institutional Capital Intelligence Layer

Commit 19: Multi-Strategy Capital Orchestration Platform.

This package provides institutional-grade capital management:
- Capital Pool & Account management
- Strategy-level capital allocation
- Portfolio-level capacity planning
- Capital efficiency measurement
- Multi-strategy exposure & overlap analysis
- Dynamic reallocation engine
- Capital stress & scenario simulation
- Capital governance (integrating with Autonomous Control Plane)
"""

from .capital_intelligence import CapitalIntelligence
from .capital_runtime import CapitalRuntime
from .capital_manager import CapitalManager
from .capital_controller import CapitalController
from .capital_orchestrator import CapitalOrchestrator

from .capital_pool import CapitalPool
from .capital_account import CapitalAccount
from .capital_allocation import CapitalAllocation
from .capital_allocator import CapitalAllocator
from .capital_budget import CapitalBudget
from .capital_reservation import CapitalReservation
from .capital_release import CapitalRelease

from .strategy_pool import StrategyPool
from .strategy_allocator import StrategyAllocator
from .strategy_capacity import StrategyCapacity
from .strategy_allocation import StrategyAllocation
from .strategy_exposure import StrategyExposure
from .strategy_dependency import StrategyDependency

from .portfolio_pool import PortfolioPool
from .portfolio_allocator import PortfolioAllocator
from .portfolio_capacity import PortfolioCapacity
from .portfolio_exposure import PortfolioExposure

from .capital_efficiency import CapitalEfficiency
from .return_on_capital import ReturnOnCapital
from .risk_adjusted_capital import RiskAdjustedCapital
from .marginal_capital_efficiency import MarginalCapitalEfficiency
from .capital_utilization import CapitalUtilization
from .capacity_efficiency import CapacityEfficiency

from .exposure_matrix import ExposureMatrix
from .strategy_correlation import StrategyCorrelation
from .factor_overlap import FactorOverlap
from .liquidity_overlap import LiquidityOverlap
from .risk_overlap import RiskOverlap

from .allocation_optimizer import AllocationOptimizer
from .allocation_constraints import AllocationConstraints
from .allocation_objective import AllocationObjective
from .allocation_scorer import AllocationScorer
from .allocation_simulator import AllocationSimulator

from .capital_scenario import CapitalScenario
from .capital_stress import CapitalStress
from .capital_shock import CapitalShock
from .liquidity_stress import LiquidityStress

from .capital_decision import CapitalDecision
from .allocation_decision import AllocationDecision
from .reallocation_decision import ReallocationDecision
from .capital_guard import CapitalGuard

from .capital_memory import CapitalMemory
from .allocation_memory import AllocationMemory
from .capacity_memory import CapacityMemory

from .metrics import InstitutionalCapitalMetrics
from .telemetry import InstitutionalCapitalTelemetry
from .diagnostics import InstitutionalCapitalDiagnostics
from .health import InstitutionalCapitalHealth

__all__ = [
    # Core
    "CapitalIntelligence",
    "CapitalRuntime",
    "CapitalManager",
    "CapitalController",
    "CapitalOrchestrator",
    # Capital Pool
    "CapitalPool",
    "CapitalAccount",
    "CapitalAllocation",
    "CapitalAllocator",
    "CapitalBudget",
    "CapitalReservation",
    "CapitalRelease",
    # Strategy Pool
    "StrategyPool",
    "StrategyAllocator",
    "StrategyCapacity",
    "StrategyAllocation",
    "StrategyExposure",
    "StrategyDependency",
    # Portfolio Pool
    "PortfolioPool",
    "PortfolioAllocator",
    "PortfolioCapacity",
    "PortfolioExposure",
    # Capital Efficiency
    "CapitalEfficiency",
    "ReturnOnCapital",
    "RiskAdjustedCapital",
    "MarginalCapitalEfficiency",
    "CapitalUtilization",
    "CapacityEfficiency",
    # Exposure
    "ExposureMatrix",
    "StrategyCorrelation",
    "FactorOverlap",
    "LiquidityOverlap",
    "RiskOverlap",
    # Allocation Optimizer
    "AllocationOptimizer",
    "AllocationConstraints",
    "AllocationObjective",
    "AllocationScorer",
    "AllocationSimulator",
    # Scenarios
    "CapitalScenario",
    "CapitalStress",
    "CapitalShock",
    "LiquidityStress",
    # Decisions
    "CapitalDecision",
    "AllocationDecision",
    "ReallocationDecision",
    "CapitalGuard",
    # Memory
    "CapitalMemory",
    "AllocationMemory",
    "CapacityMemory",
    # Observability
    "InstitutionalCapitalMetrics",
    "InstitutionalCapitalTelemetry",
    "InstitutionalCapitalDiagnostics",
    "InstitutionalCapitalHealth",
]
