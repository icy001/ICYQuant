"""
Institutional Multi-Strategy Portfolio Orchestration Layer

Commit 19 Part 1.2: Multi-Strategy Portfolio Coordination.

This package provides institutional-grade multi-strategy management:
- Strategy registry, grouping, clustering, relationship & dependency
- Signal aggregation, netting, conflict resolution & confidence weighting
- Position netting, aggregation, conflict resolution & target position
- Portfolio construction, optimization, allocation & weight/constraint engine
- Cross-strategy risk aggregation, risk contribution & factor risk
- Capital coordination, routing, priority & conflict resolution
- Rebalance engine, scheduler, trigger, optimizer, turnover/drift control
- Scenario, stress, simulation for portfolio resilience
- Orchestration decisions, policies & guards (integrating with Control Plane)
"""

from .multi_strategy_portfolio import MultiStrategyPortfolio
from .portfolio_orchestrator import PortfolioOrchestrator
from .portfolio_runtime import PortfolioRuntime
from .portfolio_manager import PortfolioManager
from .portfolio_controller import PortfolioController
from .portfolio_gateway import PortfolioGateway

from .strategy_registry import StrategyRegistry
from .strategy_group import StrategyGroup
from .strategy_cluster import StrategyCluster
from .strategy_relationship import StrategyRelationship
from .strategy_dependency import StrategyDependency
from .strategy_priority import StrategyPriority

from .strategy_signal_aggregator import StrategySignalAggregator
from .signal_netting_engine import SignalNettingEngine
from .signal_conflict_resolver import SignalConflictResolver
from .signal_priority_engine import SignalPriorityEngine
from .signal_confidence_aggregator import SignalConfidenceAggregator

from .position_netting_engine import PositionNettingEngine
from .position_aggregator import PositionAggregator
from .position_conflict_resolver import PositionConflictResolver
from .target_position_engine import TargetPositionEngine
from .net_position_engine import NetPositionEngine

from .portfolio_builder import PortfolioBuilder
from .portfolio_optimizer import PortfolioOptimizer
from .portfolio_allocator import PortfolioAllocator
from .portfolio_weight_engine import PortfolioWeightEngine
from .portfolio_constraint_engine import PortfolioConstraintEngine

from .risk_aggregator import RiskAggregator
from .cross_strategy_risk import CrossStrategyRisk
from .strategy_risk_contribution import StrategyRiskContribution
from .portfolio_risk_contribution import PortfolioRiskContribution
from .marginal_portfolio_risk import MarginalPortfolioRisk
from .aggregate_factor_risk import AggregateFactorRisk

from .capital_coordinator import CapitalCoordinator
from .strategy_capital_router import StrategyCapitalRouter
from .capital_priority_engine import CapitalPriorityEngine
from .capital_conflict_resolver import CapitalConflictResolver

from .rebalance_engine import RebalanceEngine
from .rebalance_scheduler import RebalanceScheduler
from .rebalance_trigger import RebalanceTrigger
from .rebalance_optimizer import RebalanceOptimizer
from .turnover_controller import TurnoverController
from .drift_controller import DriftController

from .portfolio_scenario import PortfolioScenario
from .portfolio_stress import PortfolioStress
from .portfolio_simulator import PortfolioSimulator

from .orchestration_decision import OrchestrationDecision
from .orchestration_policy import OrchestrationPolicy
from .orchestration_guard import OrchestrationGuard

from .portfolio_memory import PortfolioMemory
from .strategy_memory import StrategyMemory
from .rebalance_memory import RebalanceMemory

from .metrics import PortfolioMetrics
from .telemetry import PortfolioTelemetry
from .diagnostics import PortfolioDiagnostics
from .health import PortfolioHealth

__all__ = [
    "MultiStrategyPortfolio",
    "PortfolioOrchestrator",
    "PortfolioRuntime",
    "PortfolioManager",
    "PortfolioController",
    "PortfolioGateway",
    "StrategyRegistry",
    "StrategyGroup",
    "StrategyCluster",
    "StrategyRelationship",
    "StrategyDependency",
    "StrategyPriority",
    "StrategySignalAggregator",
    "SignalNettingEngine",
    "SignalConflictResolver",
    "SignalPriorityEngine",
    "SignalConfidenceAggregator",
    "PositionNettingEngine",
    "PositionAggregator",
    "PositionConflictResolver",
    "TargetPositionEngine",
    "NetPositionEngine",
    "PortfolioBuilder",
    "PortfolioOptimizer",
    "PortfolioAllocator",
    "PortfolioWeightEngine",
    "PortfolioConstraintEngine",
    "RiskAggregator",
    "CrossStrategyRisk",
    "StrategyRiskContribution",
    "PortfolioRiskContribution",
    "MarginalPortfolioRisk",
    "AggregateFactorRisk",
    "CapitalCoordinator",
    "StrategyCapitalRouter",
    "CapitalPriorityEngine",
    "CapitalConflictResolver",
    "RebalanceEngine",
    "RebalanceScheduler",
    "RebalanceTrigger",
    "RebalanceOptimizer",
    "TurnoverController",
    "DriftController",
    "PortfolioScenario",
    "PortfolioStress",
    "PortfolioSimulator",
    "OrchestrationDecision",
    "OrchestrationPolicy",
    "OrchestrationGuard",
    "PortfolioMemory",
    "StrategyMemory",
    "RebalanceMemory",
    "PortfolioMetrics",
    "PortfolioTelemetry",
    "PortfolioDiagnostics",
    "PortfolioHealth",
]
