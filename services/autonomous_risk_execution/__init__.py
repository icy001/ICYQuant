"""
Autonomous Risk & Execution Optimization Platform.

Commit 18 Part 1.4: Risk Optimization → Execution Optimization → Feedback → Learning.

Architecture:
    Target Position → Risk Optimizer → Risk-Adjusted Target
        → Execution Optimizer → Order Plan → OMS/EMS
        → Execution → Fill Result → Execution Learning ↺

Key modules:
    - Risk Optimization: dynamic budget, exposure, leverage, concentration,
      correlation, liquidity, drawdown, volatility, regime-aware
    - Risk Engines: portfolio, marginal, incremental, factor, scenario,
      stress, tail risk, VaR, expected shortfall
    - Execution Optimization: planner, scheduler, strategy selector,
      order slicing, participation, routing, timing, urgency, slippage,
      market impact, transaction cost, fill probability
    - Pre-Trade Guards: optimizer, guard, constraints, kill switch
    - Execution Feedback: fill analysis, slippage analysis,
      implementation shortfall, quality scoring, learning, memory
"""

__version__ = "0.4.0-alpha2"
__all__ = [
    # Platform
    "RiskExecutionPlatform",
    "RiskExecutionRuntime",
    "RiskExecutionManager",
    "RiskExecutionController",
    "RiskExecutionGateway",
    "RiskExecutionOrchestrator",
    # Risk Optimization
    "RiskOptimizer",
    "DynamicRiskBudget",
    "RiskBudgetEngine",
    "RiskAllocator",
    "ExposureOptimizer",
    "LeverageOptimizer",
    "ConcentrationOptimizer",
    "CorrelationOptimizer",
    "LiquidityOptimizer",
    "DrawdownController",
    "VolatilityController",
    "RegimeRiskController",
    # Risk Engines
    "PortfolioRiskEngine",
    "MarginalRiskEngine",
    "IncrementalRiskEngine",
    "FactorRiskEngine",
    "ScenarioEngine",
    "StressEngine",
    "TailRiskEngine",
    "VaREngine",
    "ExpectedShortfallEngine",
    # Execution Optimization
    "ExecutionOptimizer",
    "ExecutionScheduler",
    "ExecutionPlanner",
    "ExecutionPolicy",
    "ExecutionStrategySelector",
    "OrderSlicer",
    "ChildOrderGenerator",
    "ParticipationController",
    "LiquidityRouter",
    "VenueSelector",
    "TimingOptimizer",
    "UrgencyController",
    "SlippageOptimizer",
    "MarketImpactModel",
    "TransactionCostModel",
    "SpreadModel",
    "FillProbability",
    "ExecutionCostEstimator",
    # Pre-Trade Guards
    "PreTradeOptimizer",
    "PreTradeGuard",
    "OrderConstraintEngine",
    "ExecutionGuard",
    "KillSwitch",
    # Execution Feedback
    "ExecutionFeedback",
    "FillAnalyzer",
    "SlippageAnalyzer",
    "ImplementationShortfall",
    "ExecutionQuality",
    "ExecutionLearning",
    "ExecutionMemory",
    # Memory
    "RiskMemory",
    "ScenarioMemory",
    "OptimizationMemory",
    "LineageTracker",
    # Control
    "Policy",
    "BudgetController",
    "Metrics",
    "Telemetry",
    "Diagnostics",
    "Health",
]
