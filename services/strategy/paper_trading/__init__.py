"""
ICYQuant Paper Trading Platform
================================
Paper trading, execution simulation, strategy evaluation, and promotion workflow.

This package provides the final validation environment where strategies are
paper-traded with realistic market simulations before being promoted to live.
"""

from services.strategy.paper_trading.paper_trading_engine import (
    PaperTradingEngine,
    PaperTrade,
    PaperOrder,
    PaperOrderStatus,
    PaperSessionStatus,
)

from services.strategy.paper_trading.paper_runtime import (
    PaperRuntime,
    PaperConfig,
)

from services.strategy.paper_trading.paper_session import (
    PaperSession,
    SessionPhase,
)

from services.strategy.paper_trading.paper_manager import (
    PaperManager,
    ManagerEvent,
)

from services.strategy.paper_trading.virtual_exchange import (
    VirtualExchange,
    OrderBook,
    OrderBookLevel,
    OrderBookSide,
)

from services.strategy.paper_trading.virtual_oms import (
    VirtualOMS,
    OmsOrder,
    OmsOrderState,
    OmsFill,
)

from services.strategy.paper_trading.virtual_portfolio import (
    VirtualPortfolio,
    VirtualPosition,
    VirtualBalance,
)

from services.strategy.paper_trading.virtual_account import (
    VirtualAccount,
    AccountCurrency,
    VirtualTransaction,
)

from services.strategy.paper_trading.execution_simulator import (
    ExecutionSimulator,
    ExecutionResult,
    FillDetail,
)

from services.strategy.paper_trading.matching_engine import (
    MatchingEngine,
    MatchResult,
    MatchStatus,
)

from services.strategy.paper_trading.slippage_simulator import (
    SlippageSimulator,
    SlippageModel,
    SlippageResult,
)

from services.strategy.paper_trading.commission_simulator import (
    CommissionSimulator,
    CommissionSchedule,
    CommissionResult,
)

from services.strategy.paper_trading.latency_simulator import (
    LatencySimulator,
    LatencyProfile,
    LatencyResult,
)

from services.strategy.paper_trading.liquidity_simulator import (
    LiquiditySimulator,
    LiquidityProfile,
    LiquidityResult,
)

from services.strategy.paper_trading.market_impact_simulator import (
    MarketImpactSimulator,
    ImpactModel,
    ImpactResult,
)

from services.strategy.paper_trading.benchmark_engine import (
    BenchmarkEngine,
    BenchmarkType,
    BenchmarkResult,
)

from services.strategy.paper_trading.performance_evaluator import (
    PerformanceEvaluator,
    PerformanceReport,
    PerformanceMetrics,
)

from services.strategy.paper_trading.attribution_engine import (
    AttributionEngine,
    AttributionReport,
    AttributionFactor,
)

from services.strategy.paper_trading.strategy_scorecard import (
    StrategyScorecard,
    ScorecardResult,
    ScoreDimension,
)

from services.strategy.paper_trading.promotion_workflow import (
    PromotionWorkflow,
    PromotionStage,
    PromotionDecision,
    PromotionRequest,
)

from services.strategy.paper_trading.approval_manager import (
    ApprovalManager,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalLevel,
)

from services.strategy.paper_trading.kill_switch import (
    KillSwitch,
    KillSwitchRule,
    KillSwitchEvent,
    KillReason,
)

from services.strategy.paper_trading.continuous_evaluation import (
    ContinuousEvaluation,
    EvaluationWindow,
    EvaluationAlert,
    EvaluationStatus,
)

from services.strategy.paper_trading.diagnostics import (
    PaperTradingDiagnostics,
    PTDiagnosticReport,
)

from services.strategy.paper_trading.metrics import PaperTradingMetrics

from services.strategy.paper_trading.telemetry import PaperTradingTelemetry

from services.strategy.paper_trading.health import PaperTradingHealthChecker

__all__ = [
    # Paper Trading Engine
    "PaperTradingEngine",
    "PaperTrade",
    "PaperOrder",
    "PaperOrderStatus",
    "PaperSessionStatus",
    "PaperRuntime",
    "PaperConfig",
    "PaperSession",
    "SessionPhase",
    "PaperManager",
    "ManagerEvent",
    # Virtual Exchange
    "VirtualExchange",
    "OrderBook",
    "OrderBookLevel",
    "OrderBookSide",
    "VirtualOMS",
    "OmsOrder",
    "OmsOrderState",
    "OmsFill",
    "VirtualPortfolio",
    "VirtualPosition",
    "VirtualBalance",
    "VirtualAccount",
    "AccountCurrency",
    "VirtualTransaction",
    # Execution Simulation
    "ExecutionSimulator",
    "ExecutionResult",
    "FillDetail",
    "MatchingEngine",
    "MatchResult",
    "MatchStatus",
    "SlippageSimulator",
    "SlippageModel",
    "SlippageResult",
    "CommissionSimulator",
    "CommissionSchedule",
    "CommissionResult",
    # Market Simulation
    "LatencySimulator",
    "LatencyProfile",
    "LatencyResult",
    "LiquiditySimulator",
    "LiquidityProfile",
    "LiquidityResult",
    "MarketImpactSimulator",
    "ImpactModel",
    "ImpactResult",
    # Evaluation
    "BenchmarkEngine",
    "BenchmarkType",
    "BenchmarkResult",
    "PerformanceEvaluator",
    "PerformanceReport",
    "PerformanceMetrics",
    "AttributionEngine",
    "AttributionReport",
    "AttributionFactor",
    "StrategyScorecard",
    "ScorecardResult",
    "ScoreDimension",
    # Promotion & Safety
    "PromotionWorkflow",
    "PromotionStage",
    "PromotionDecision",
    "PromotionRequest",
    "ApprovalManager",
    "ApprovalRequest",
    "ApprovalStatus",
    "ApprovalLevel",
    "KillSwitch",
    "KillSwitchRule",
    "KillSwitchEvent",
    "KillReason",
    "ContinuousEvaluation",
    "EvaluationWindow",
    "EvaluationAlert",
    "EvaluationStatus",
    # Observability
    "PaperTradingDiagnostics",
    "PTDiagnosticReport",
    "PaperTradingMetrics",
    "PaperTradingTelemetry",
    "PaperTradingHealthChecker",
]
