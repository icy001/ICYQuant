"""Portfolio Management API — unified endpoint for all portfolio operations."""

import time
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.portfolio_management.portfolio_manager import (
    PortfolioManager, PortfolioConfig, PortfolioType, PortfolioStatus,
)
from services.portfolio_management.capital_allocator import (
    CapitalAllocator, AllocationMethod, AllocationRequest,
)
from services.portfolio_management.risk_budget import RiskBudgetManager, RiskBudgetType
from services.portfolio_management.optimizer import (
    PortfolioOptimizer, OptimizationConfig, OptimizationMethod,
)
from services.portfolio_management.rebalancer import (
    PortfolioRebalancer, RebalanceConfig, RebalanceMethod,
)
from services.portfolio_management.performance import (
    PerformanceCalculator, PerformanceConfig,
)
from services.portfolio_management.attribution import AttributionEngine
from services.portfolio_management.benchmark import BenchmarkManager
from services.portfolio_management.account_manager import AccountManager, AccountType
from services.portfolio_management.fund_manager import FundManager, FoFConfig
from services.portfolio_management.reporting import (
    ReportingEngine, ReportType, ExportFormat,
)

logger = logging.getLogger(__name__)


@dataclass
class APIResponse:
    """Standard API response wrapper."""

    success: bool = True
    data: Any = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "warnings": self.warnings,
            "timestamp": self.timestamp,
        }


class PortfolioAPI:
    """Unified API for all portfolio management operations.

    Provides a single interface for:
    - Portfolio CRUD and management
    - Capital allocation
    - Risk budget management
    - Portfolio optimization
    - Rebalancing
    - Performance calculation
    - Attribution analysis
    - Benchmark management
    - Account management
    - Fund of Funds management
    - Report generation
    """

    def __init__(self):
        self.portfolio_manager = PortfolioManager()
        self.capital_allocator = CapitalAllocator()
        self.risk_budget_mgr = RiskBudgetManager()
        self.optimizer = PortfolioOptimizer()
        self.rebalancer = PortfolioRebalancer()
        self.performance_calc = PerformanceCalculator()
        self.attribution_engine = AttributionEngine()
        self.benchmark_mgr = BenchmarkManager()
        self.account_mgr = AccountManager()
        self.fund_mgr = FundManager()
        self.reporting_engine = ReportingEngine()

    # ---- Portfolio Management ----

    def create_portfolio(self, config: Dict[str, Any]) -> APIResponse:
        try:
            portfolio = self.portfolio_manager.create_portfolio(
                PortfolioConfig(**config)
            )
            return APIResponse(data={
                "portfolio_id": portfolio.portfolio_id,
                "name": portfolio.config.name,
                "status": portfolio.status.value,
            })
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    def list_portfolios(
        self, portfolio_type: Optional[str] = None, status: Optional[str] = None
    ) -> APIResponse:
        try:
            pt = PortfolioType(portfolio_type) if portfolio_type else None
            ps = PortfolioStatus(status) if status else None
            portfolios = self.portfolio_manager.list_portfolios(
                portfolio_type=pt, status=ps
            )
            return APIResponse(data={
                "count": len(portfolios),
                "portfolios": [
                    {
                        "id": p.portfolio_id,
                        "name": p.config.name,
                        "type": p.config.portfolio_type.value,
                        "status": p.status.value,
                        "nav": p.nav,
                    }
                    for p in portfolios
                ],
            })
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    def get_portfolio(self, portfolio_id: str) -> APIResponse:
        try:
            portfolio = self.portfolio_manager.get_portfolio(portfolio_id)
            if not portfolio:
                return APIResponse(success=False, error="Portfolio not found")
            return APIResponse(data={
                "portfolio_id": portfolio.portfolio_id,
                "name": portfolio.config.name,
                "type": portfolio.config.portfolio_type.value,
                "status": portfolio.status.value,
                "nav": portfolio.nav,
                "positions": [
                    p.to_dict() for p in self.portfolio_manager.get_positions(portfolio_id)
                ],
            })
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    def add_position(self, portfolio_id: str, position: Dict[str, Any]) -> APIResponse:
        try:
            from infrastructure.portfolio.portfolio_store import PositionRecord
            result = self.portfolio_manager.add_position(
                portfolio_id, PositionRecord(**position)
            )
            if result:
                return APIResponse(data={"position_id": result.position_id})
            return APIResponse(success=False, error="Failed to add position")
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ---- Capital Allocation ----

    def allocate_capital(self, request: Dict[str, Any]) -> APIResponse:
        try:
            rules_data = request.pop("rules", [])
            from services.portfolio_management.capital_allocator import AllocationRule
            rules = [AllocationRule(**r) for r in rules_data]
            req = AllocationRequest(**{**request, "rules": rules})
            result = self.capital_allocator.allocate(req)
            return APIResponse(data={
                "total_allocated": result.total_allocated,
                "allocations": result.allocations,
                "weights": result.weights,
                "method": result.method.value,
            })
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ---- Risk Budget ----

    def create_risk_budget(
        self, portfolio_id: str, name: str, total_risk: float
    ) -> APIResponse:
        try:
            budget = self.risk_budget_mgr.create_budget(portfolio_id, name, total_risk)
            return APIResponse(data={"budget_id": budget.budget_id})
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    def check_risk(self, portfolio_id: str, metrics: Dict[str, float]) -> APIResponse:
        try:
            results = self.risk_budget_mgr.check_portfolio_risk(portfolio_id, metrics)
            return APIResponse(data=results)
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ---- Optimization ----

    def optimize_portfolio(
        self,
        expected_returns: Dict[str, float],
        method: str = "max_sharpe",
        constraints: Optional[Dict[str, Any]] = None,
    ) -> APIResponse:
        try:
            opt_config = OptimizationConfig(
                method=OptimizationMethod(method),
            )
            self.optimizer.config = opt_config
            result = self.optimizer.optimize(expected_returns)
            return APIResponse(data={
                "weights": result.weights,
                "expected_return": result.expected_return,
                "expected_risk": result.expected_risk,
                "expected_sharpe": result.expected_sharpe,
                "method": result.method.value,
            })
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ---- Rebalance ----

    def rebalance(
        self,
        portfolio_id: str,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        nav: float,
        prices: Dict[str, float],
    ) -> APIResponse:
        try:
            result = self.rebalancer.rebalance(
                portfolio_id, current_weights, target_weights, nav, prices
            )
            return APIResponse(data={
                "triggered": result.triggered,
                "reason": result.trigger_reason,
                "positions_rebalanced": result.positions_rebalanced,
                "turnover_pct": result.estimated_turnover_pct,
                "trade_count": len(result.trade_list.trades) if result.trade_list else 0,
            })
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ---- Performance ----

    def calculate_performance(
        self,
        portfolio_id: str,
        returns: List[float],
        benchmark_returns: Optional[List[float]] = None,
    ) -> APIResponse:
        try:
            metrics = self.performance_calc.calculate_metrics(
                portfolio_id, returns, benchmark_returns
            )
            return APIResponse(data={
                "total_return": metrics.total_return,
                "annual_return": metrics.annual_return,
                "sharpe_ratio": metrics.sharpe_ratio,
                "max_drawdown": metrics.max_drawdown,
                "volatility": metrics.volatility_annual,
                "sortino_ratio": metrics.sortino_ratio,
            })
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ---- Reporting ----

    def generate_report(
        self,
        report_type: str,
        title: str,
        portfolio_ids: List[str],
        data: Dict[str, Any],
        export_format: str = "json",
    ) -> APIResponse:
        try:
            rt = ReportType(report_type)
            report = self.reporting_engine.generate_report(
                report_type=rt,
                title=title,
                portfolio_ids=portfolio_ids,
                data=data,
            )
            export = self.reporting_engine.export_report(
                report.report_id, ExportFormat(export_format)
            )
            return APIResponse(data={
                "report_id": report.report_id,
                "export": export[:1000] + "..." if export and len(export) > 1000 else export,
            })
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ---- Summary ----

    def get_system_summary(self) -> APIResponse:
        try:
            return APIResponse(data={
                "portfolios": self.portfolio_manager.get_summary(),
                "capital": self.capital_allocator.get_summary(),
                "risk": self.risk_budget_mgr.get_summary(),
                "accounts": self.account_mgr.get_summary(),
                "funds": self.fund_mgr.get_summary(),
                "benchmarks": self.benchmark_mgr.get_summary(),
                "reports": self.reporting_engine.get_summary(),
            })
        except Exception as e:
            return APIResponse(success=False, error=str(e))
