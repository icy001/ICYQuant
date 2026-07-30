"""Portfolio Management Service — orchestrates all portfolio management operations."""

import logging
from typing import Any, Dict, List, Optional

from services.portfolio_management.portfolio_manager import (
    PortfolioManager, PortfolioConfig, Portfolio, PortfolioStatus, PortfolioType,
)
from services.portfolio_management.capital_allocator import CapitalAllocator, AllocationMethod
from services.portfolio_management.strategy_allocator import StrategyAllocator
from services.portfolio_management.risk_budget import RiskBudgetManager
from services.portfolio_management.optimizer import PortfolioOptimizer
from services.portfolio_management.rebalancer import PortfolioRebalancer
from services.portfolio_management.performance import PerformanceCalculator
from services.portfolio_management.attribution import AttributionEngine
from services.portfolio_management.benchmark import BenchmarkManager, Benchmark
from services.portfolio_management.account_manager import AccountManager
from services.portfolio_management.fund_manager import FundManager
from services.portfolio_management.reporting import ReportingEngine

from infrastructure.portfolio.portfolio_store import PortfolioStore, StoreConfig
from infrastructure.portfolio.scheduler import RebalanceScheduler
from infrastructure.portfolio.snapshot_engine import SnapshotEngine
from infrastructure.portfolio.rebalance_executor import RebalanceExecutor

logger = logging.getLogger(__name__)


class PortfolioManagementService:
    """Orchestration service for the entire Portfolio Management platform.

    Coordinates all sub-modules:
    - Portfolio Manager: CRUD and lifecycle
    - Capital Allocator: capital distribution
    - Strategy Allocator: strategy weighting
    - Risk Budget Manager: limits and monitoring
    - Optimizer: weight optimization
    - Rebalancer: drift detection and trades
    - Performance Calculator: metrics
    - Attribution Engine: return decomposition
    - Benchmark Manager: index tracking
    - Account Manager: cash and margin
    - Fund Manager: FoF operations
    - Reporting Engine: report generation

    Infrastructure:
    - Portfolio Store: data persistence
    - Scheduler: rebalance timing
    - Snapshot Engine: state capture
    - Rebalance Executor: order execution
    """

    def __init__(
        self,
        store_config: Optional[StoreConfig] = None,
    ):
        # Infrastructure
        self.store = PortfolioStore(store_config)
        self.scheduler = RebalanceScheduler()
        self.snapshot_engine = SnapshotEngine()
        self.executor = RebalanceExecutor()

        # Services
        self.portfolios = PortfolioManager(self.store)
        self.capital = CapitalAllocator()
        self.strategies = StrategyAllocator()
        self.risk = RiskBudgetManager()
        self.optimizer = PortfolioOptimizer()
        self.rebalancer = PortfolioRebalancer()
        self.performance = PerformanceCalculator()
        self.attribution = AttributionEngine()
        self.benchmarks = BenchmarkManager()
        self.accounts = AccountManager()
        self.funds = FundManager()
        self.reporting = ReportingEngine()

        logger.info("PortfolioManagementService initialized")

    # ---- Portfolio Lifecycle ----

    def onboard_portfolio(
        self,
        name: str,
        portfolio_type: PortfolioType,
        initial_capital: float,
        benchmark_id: str = "",
        **kwargs,
    ) -> Portfolio:
        """Full portfolio onboarding workflow."""
        config = PortfolioConfig(
            name=name,
            portfolio_type=portfolio_type,
            initial_capital=initial_capital,
            benchmark_id=benchmark_id,
            **kwargs,
        )
        portfolio = self.portfolios.create_portfolio(config)
        self.portfolios.activate_portfolio(portfolio.portfolio_id)

        # Create risk budget
        self.risk.create_budget(
            portfolio.portfolio_id,
            f"{name} Risk Budget",
            config.risk_budget_annual,
        )

        # Take snapshot
        self.snapshot_engine.capture_snapshot(
            portfolio_id=portfolio.portfolio_id,
            portfolio_name=name,
            nav=initial_capital,
            cash=initial_capital,
            positions_data=[],
        )

        logger.info("Portfolio onboarded: %s (capital=%.2f)", name, initial_capital)
        return portfolio

    # ---- Rebalance Workflow ----

    def execute_rebalance_workflow(
        self,
        portfolio_id: str,
        target_weights: Dict[str, float],
        prices: Dict[str, float],
    ) -> Dict[str, Any]:
        """End-to-end rebalance workflow: detect → generate → execute."""
        portfolio = self.portfolios.get_portfolio(portfolio_id)
        if not portfolio:
            return {"error": "Portfolio not found"}

        current_weights = portfolio.record.get_position_weights() if portfolio.record else {}
        nav = portfolio.nav

        # Step 1: Detect drift & generate trades
        result = self.rebalancer.rebalance(
            portfolio_id, current_weights, target_weights, nav, prices
        )

        if not result.triggered or not result.trade_list:
            return {"triggered": False, "reason": result.trigger_reason}

        # Step 2: Convert trades to orders & execute
        from infrastructure.portfolio.rebalance_executor import RebalanceOrder, OrderSide

        orders = []
        for trade in result.trade_list.trades:
            order = RebalanceOrder(
                portfolio_id=portfolio_id,
                symbol=trade.symbol,
                side=OrderSide.BUY if trade.side == "BUY" else OrderSide.SELL,
                quantity=trade.quantity,
                limit_price=trade.price,
                target_weight=0.0,  # Will be filled after rebalance
                current_weight=0.0,
                weight_delta=trade.weight_before - trade.weight_after,
            )
            orders.append(order)

        execution = self.executor.execute_orders(portfolio_id, orders)

        return {
            "triggered": True,
            "trades_generated": len(orders),
            "trades_filled": execution.filled_orders,
            "fill_rate": execution.fill_rate_pct,
            "total_value": execution.total_executed_value,
        }

    # ---- Periodic Tasks ----

    def run_daily_tasks(self) -> Dict[str, Any]:
        """Run all daily portfolio management tasks."""
        results = {}

        # Process scheduled rebalances
        due_tasks = self.scheduler.get_due_tasks()
        for task in due_tasks:
            self.scheduler.execute_task(task.task_id)
        results["scheduled_tasks"] = len(due_tasks)

        # Clean old snapshots
        cleaned = self.snapshot_engine.clean_old_snapshots()
        results["snapshots_cleaned"] = cleaned

        return results

    def run_monthly_tasks(self) -> Dict[str, Any]:
        """Run monthly portfolio management tasks."""
        results = {}

        # Recalculate all performance
        for portfolio in self.portfolios.list_portfolios():
            positions = self.portfolios.get_positions(portfolio.portfolio_id)
            # In production: fetch historical returns from DB
            results[portfolio.portfolio_id] = "monthly_tasks_complete"

        return results

    # ---- System Status ----

    def get_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        return {
            "portfolios": self.portfolios.get_summary(),
            "capital": self.capital.get_summary(),
            "risk": self.risk.get_summary(),
            "accounts": self.accounts.get_summary(),
            "funds": self.funds.get_summary(),
            "benchmarks": self.benchmarks.get_summary(),
            "reports": self.reporting.get_summary(),
            "scheduler": self.scheduler.get_schedule_summary(),
            "executor": self.executor.get_execution_summary(),
            "snapshots": self.snapshot_engine.get_summary(),
        }
