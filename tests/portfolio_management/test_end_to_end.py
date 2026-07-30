"""End-to-end integration tests for Portfolio Management."""

import pytest
from services.portfolio_management.service import PortfolioManagementService
from services.portfolio_management.portfolio_manager import (
    PortfolioType, PortfolioConfig,
)
from infrastructure.portfolio.portfolio_store import (
    AssetClass, Currency, PositionRecord,
)


class TestEndToEnd:
    """End-to-end portfolio management workflow tests."""

    @pytest.fixture
    def service(self):
        return PortfolioManagementService()

    def test_full_portfolio_lifecycle(self, service):
        """Test: Create → Activate → Add Positions → Rebalance → Close."""
        # 1. Onboard portfolio
        portfolio = service.onboard_portfolio(
            name="E2E Test Portfolio",
            portfolio_type=PortfolioType.HYBRID,
            initial_capital=10_000_000,
        )
        assert portfolio.is_active

        # 2. Add positions
        positions = [
            PositionRecord(symbol="000001.SZ", asset_class=AssetClass.EQUITY,
                          quantity=20000, avg_cost=15.0, current_price=16.5,
                          market_value=330000, sector="Financials"),
            PositionRecord(symbol="600519.SH", asset_class=AssetClass.EQUITY,
                          quantity=5000, avg_cost=1800, current_price=1900,
                          market_value=9500000, sector="Consumer"),
        ]
        for pos in positions:
            result = service.portfolios.add_position(portfolio.portfolio_id, pos)
            assert result is not None

        # 3. Check positions
        stored_positions = service.portfolios.get_positions(portfolio.portfolio_id)
        assert len(stored_positions) == 2

        # 4. Take snapshot
        snapshot = service.snapshot_engine.capture_snapshot(
            portfolio_id=portfolio.portfolio_id,
            portfolio_name=portfolio.config.name,
            nav=10_000_000,
            cash=170000,
            positions_data=[p.to_dict() for p in stored_positions],
        )
        assert snapshot is not None
        assert snapshot.position_count == 2

        # 5. Calculate performance
        sample_returns = [0.001 * (i % 5 - 2) for i in range(100)]  # mixed returns
        metrics = service.performance.calculate_metrics(
            portfolio.portfolio_id, sample_returns
        )
        assert metrics.portfolio_id == portfolio.portfolio_id

        # 6. Close portfolio
        service.portfolios.close_portfolio(portfolio.portfolio_id)
        p = service.portfolios.get_portfolio(portfolio.portfolio_id)
        assert p.status.value == "closed"

    def test_capital_allocation_workflow(self, service):
        """Test: Create pools → Allocate → Check flows."""
        # Create capital pool
        pool = service.capital.create_pool("Strategy Pool", 100_000_000)

        # Create allocation rules
        from services.portfolio_management.capital_allocator import (
            AllocationRule, AllocationRequest, AllocationMethod,
        )
        rules = [
            AllocationRule(name="Alpha", target_id="alpha_strat", min_allocation=0),
            AllocationRule(name="CTA", target_id="cta_strat", min_allocation=0),
            AllocationRule(name="Market Neutral", target_id="mn_strat", min_allocation=0),
        ]

        request = AllocationRequest(
            pool_id=pool.pool_id,
            amount=90_000_000,
            method=AllocationMethod.EQUAL_WEIGHT,
            rules=rules,
        )
        result = service.capital.allocate(request)
        assert result.total_allocated > 0
        assert len(result.allocations) == 3

        # Verify pool state
        updated_pool = service.capital.get_pool(pool.pool_id)
        assert updated_pool.allocated_capital > 0

    def test_risk_monitoring_workflow(self, service):
        """Test: Create budget → Set limits → Check breaches."""
        budget = service.risk.create_budget("test-port", "Test Budget", 0.15)
        bucket = service.risk.add_bucket(budget.budget_id, "Main", "strat-1", 0.10)
        service.risk.add_default_limits(bucket)

        # All OK — use values within limits (limits are in % units)
        metrics = {"volatility": 12.0, "var_95": 0.5, "max_drawdown": 8.0, "leverage": 1.1}
        results = service.risk.check_portfolio_risk("test-port", metrics)
        assert len(results.get("breaches", [])) == 0

        # Trigger breach with high volatility (30% > 25% hard limit)
        metrics["volatility"] = 30.0
        results = service.risk.check_portfolio_risk("test-port", metrics)
        assert len(results.get("breaches", [])) > 0

    def test_optimizer_rebalancer_integration(self, service):
        """Test: Optimize → Generate weights → Rebalance."""
        returns = {
            "AAPL": 0.20, "GOOGL": 0.18, "MSFT": 0.15, "TSLA": 0.35,
            "AMZN": 0.22, "META": 0.25, "NVDA": 0.40, "JPM": 0.10,
        }

        # Optimize
        opt_result = service.optimizer.optimize(returns)

        # Use optimized weights as targets
        target_weights = opt_result.weights

        # Simulate current weights (diverged from target)
        current_weights = {k: v * (1.0 + (0.1 if i % 2 == 0 else -0.1))
                          for i, (k, v) in enumerate(target_weights.items())}

        nav = 5_000_000
        prices = {s: 100 + i * 50 for i, s in enumerate(target_weights.keys())}

        rebalance_result = service.rebalancer.rebalance(
            "port-1", current_weights, target_weights, nav, prices
        )

        assert rebalance_result is not None
        if rebalance_result.triggered:
            assert rebalance_result.trade_list is not None

    def test_benchmark_workflow(self, service):
        """Test: Register benchmark → Calculate tracking error."""
        from services.portfolio_management.benchmark import Benchmark, BenchmarkType

        benchmark = Benchmark(
            name="CSI 300",
            ticker="000300.SH",
            benchmark_type=BenchmarkType.MARKET_INDEX,
        )
        # Add some sample returns
        for _ in range(100):
            import random
            random.seed(1)
            benchmark.add_return(random.gauss(0.0003, 0.012))

        service.benchmarks.register_benchmark(benchmark)

        registered = service.benchmarks.get_benchmark(benchmark.benchmark_id)
        assert registered is not None
        assert registered.name == "CSI 300"

        # Calculate tracking error
        portfolio_returns = [0.0005] * 100  # consistent outperformance
        te = service.benchmarks.calculate_tracking_error(
            "port-1", benchmark.benchmark_id, portfolio_returns
        )
        assert te.benchmark_id == benchmark.benchmark_id
        assert te.n_periods > 0

    def test_account_workflow(self, service):
        """Test: Create account → Deposit → Link portfolio."""
        from services.portfolio_management.account_manager import AccountType

        account = service.accounts.create_account(
            "Trading Account 1",
            account_type=AccountType.INSTITUTIONAL,
        )
        assert account.is_active

        # Deposit
        service.accounts.deposit(account.account_id, 10_000_000)
        assert account.cash.current_balance == 10_000_000

        # Link portfolio
        service.accounts.link_portfolio(account.account_id, "port-1")
        assert "port-1" in account.portfolio_ids

        # Freeze cash
        service.accounts.freeze_cash(account.account_id, 1_000_000)
        assert account.cash.frozen_balance == 1_000_000
        assert account.cash.available_balance == 9_000_000

    def test_reporting_workflow(self, service):
        """Test: Generate report → Export in multiple formats."""
        from services.portfolio_management.reporting import ReportType, ExportFormat
        service.reporting.create_default_templates()

        data = {
            "summary": {"nav": 10_000_000, "return": 0.15},
            "performance": {"sharpe": 1.5, "volatility": 0.18},
            "risk": {"var_95": 0.02, "max_drawdown": -0.12},
            "attribution": {"allocation": 0.03, "selection": 0.05},
        }

        report = service.reporting.generate_report(
            report_type=ReportType.MONTHLY_REPORT,
            title="January 2026 Report",
            portfolio_ids=["port-1", "port-2"],
            data=data,
            period_start="2026-01-01",
            period_end="2026-01-31",
        )
        assert report.report_id is not None

        # Export as JSON
        json_output = service.reporting.export_report(report.report_id)
        assert json_output is not None
        assert "port-1" in json_output

        # Export as Markdown
        md_output = service.reporting.export_report(report.report_id, ExportFormat.MARKDOWN)
        assert md_output is not None
        assert "January 2026" in md_output

    def test_full_system_status(self, service):
        """Test system status aggregation."""
        service.onboard_portfolio("P1", PortfolioType.STOCK, 5_000_000)
        service.onboard_portfolio("P2", PortfolioType.CTA, 3_000_000)

        status = service.get_status()
        assert "portfolios" in status
        assert "capital" in status
        assert "risk" in status
        assert "accounts" in status
        assert "benchmarks" in status

        assert status["portfolios"]["total_portfolios"] == 2
