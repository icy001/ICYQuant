"""Institutional Event-Driven Backtesting Engine.

Commit 11 Part 1.3 — Complete backtesting system with realistic execution
simulation, transaction cost modeling, and performance attribution.

Architecture::

    Historical Dataset
            ↓
    Market Replay (market_replay)
            ↓
    Event Engine (event_engine, event_queue, event_dispatcher)
            ↓
    Strategy Runner (strategy_runner)
            ↓
    Order Simulator (order_simulator)
            ↓
    Execution Simulator (execution_simulator, matching_engine)
            ↓
    Portfolio Update
            ↓
    Performance & Attribution (performance_engine, attribution_engine)
            ↓
    Backtest Report (report_generator)

Core Engine:
    * BacktestEngine — unified entry point (initialize/execute/generate_report)
    * BacktestManager — lifecycle coordinator for all subsystems
    * BacktestRuntime — job submission, state tracking, cancellation
    * BacktestContext — shared session/trace context
    * BacktestRegistry — dynamic registration of strategies, benchmarks, cost models
    * BacktestRepository — CRUD for backtests, trades, positions, performance

Event-Driven Engine:
    * EventEngine — orchestrates event queue and dispatcher
    * MarketReplay — tick/bar historical data replay with speed control
    * EventQueue — thread-safe priority event queue
    * EventDispatcher — routes events to registered handlers
    * StrategyRunner — unified signal generation and order creation

Order & Execution:
    * OrderSimulator — Market/Limit/Stop/StopLimit order simulation
    * ExecutionSimulator — realistic fill simulation with constraints
    * MatchingEngine — price-time priority matching
    * SlippageModel — Fixed/Percentage/Volatility/Liquidity/Impact models

Cost Models:
    * TransactionCost — unified cost aggregator
    * CommissionModel — PerShare/PerOrder/Percentage/Tiered
    * TaxModel — StampDuty/TransactionTax/Regional
    * LiquidityModel — ADV/Spread/Participation/Depth based
    * LatencyModel — Network/OMS/Exchange/Matching latency
    * BorrowCost — short borrow cost model

Corporate Actions:
    * CorporateAction — Split/ReverseSplit/Merge/SpinOff
    * DividendProcessor — Cash/Stock/Dividend Reinvestment

Performance & Attribution:
    * BenchmarkEngine — SPY/QQQ/CSI300/Custom benchmarks
    * PerformanceEngine — Sharpe/Sortino/Calmar/Drawdown/Return
    * AttributionEngine — AssetAllocation/SecuritySelection/Factor/Timing
    * Statistics — comprehensive trade/position statistics

Observability:
    * BacktestMetrics — 7 Prometheus-compatible metrics
    * BacktestTracer — distributed tracing for backtest operations
    * BacktestDiagnostics — component health and dependency checks
    * BacktestHealthCheck — UP/DOWN/DEGRADED component status
"""

from .backtest_context import BacktestContext
from .backtest_engine import BacktestEngine, BacktestEngineState
from .backtest_manager import BacktestManager, BacktestManagerState
from .backtest_runtime import BacktestRuntime, BacktestRuntimeState
from .backtest_registry import BacktestRegistry
from .backtest_repository import BacktestRepository

# Event-Driven Engine
from .event_engine import EventEngine, BacktestEventType
from .market_replay import MarketReplay, ReplayMode
from .event_queue import EventQueue, BacktestEvent
from .event_dispatcher import EventDispatcher
from .strategy_runner import StrategyRunner

# Order & Execution
from .order_simulator import OrderSimulator, OrderType, OrderStatus, FillStatus
from .execution_simulator import ExecutionSimulator, ExecutionMode
from .matching_engine import MatchingEngine, MatchingResult
from .slippage_model import SlippageModel, SlippageMethod

# Cost Models
from .transaction_cost import TransactionCost, TransactionCostBreakdown
from .commission_model import CommissionModel, CommissionType
from .tax_model import TaxModel, TaxType
from .liquidity_model import LiquidityModel, LiquidityProfile
from .latency_model import LatencyModel, LatencyComponent
from .borrow_cost import BorrowCost, BorrowCostRate

# Corporate Actions & Dividends
from .corporate_action import CorporateActionProcessor, CorporateActionType
from .dividend_processor import DividendProcessor, DividendType

# Performance & Attribution
from .benchmark_engine import BenchmarkEngine
from .performance_engine import PerformanceEngine, PerformanceMetrics
from .attribution_engine import AttributionEngine, AttributionResult
from .statistics import TradeStatistics

# Report & Observability
from .report_generator import ReportGenerator, ReportFormat
from .metrics import BacktestMetrics
from .telemetry import BacktestTracer, BacktestSpan, BacktestSpanContext
from .diagnostics import BacktestDiagnostics, BacktestDiagnosticReport, BacktestDiagnosticStatus
from .health import BacktestHealthCheck

__all__ = [
    # Core Engine
    "BacktestEngine",
    "BacktestEngineState",
    "BacktestManager",
    "BacktestManagerState",
    "BacktestRuntime",
    "BacktestRuntimeState",
    "BacktestContext",
    "BacktestRegistry",
    "BacktestRepository",
    # Event-Driven Engine
    "EventEngine",
    "BacktestEventType",
    "MarketReplay",
    "ReplayMode",
    "EventQueue",
    "BacktestEvent",
    "EventDispatcher",
    "StrategyRunner",
    # Order & Execution
    "OrderSimulator",
    "OrderType",
    "OrderStatus",
    "FillStatus",
    "ExecutionSimulator",
    "ExecutionMode",
    "MatchingEngine",
    "MatchingResult",
    "SlippageModel",
    "SlippageMethod",
    # Cost Models
    "TransactionCost",
    "TransactionCostBreakdown",
    "CommissionModel",
    "CommissionType",
    "TaxModel",
    "TaxType",
    "LiquidityModel",
    "LiquidityProfile",
    "LatencyModel",
    "LatencyComponent",
    "BorrowCost",
    "BorrowCostRate",
    # Corporate Actions & Dividends
    "CorporateActionProcessor",
    "CorporateActionType",
    "DividendProcessor",
    "DividendType",
    # Performance & Attribution
    "BenchmarkEngine",
    "PerformanceEngine",
    "PerformanceMetrics",
    "AttributionEngine",
    "AttributionResult",
    "TradeStatistics",
    # Report & Observability
    "ReportGenerator",
    "ReportFormat",
    "BacktestMetrics",
    "BacktestTracer",
    "BacktestSpan",
    "BacktestSpanContext",
    "BacktestDiagnostics",
    "BacktestDiagnosticReport",
    "BacktestDiagnosticStatus",
    "BacktestHealthCheck",
]
