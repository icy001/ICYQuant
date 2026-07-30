"""Tests for Portfolio Manager."""

import pytest
from services.portfolio_management.portfolio_manager import (
    PortfolioManager, PortfolioConfig, Portfolio, PortfolioStatus,
    PortfolioGroup, AllocationTree, AllocationType, AllocationNode,
)
from infrastructure.portfolio.portfolio_store import (
    PortfolioStore, PositionRecord, AssetClass, Currency, PortfolioType,
)


class TestPortfolioManager:
    """Test multi-portfolio manager."""

    @pytest.fixture
    def manager(self):
        return PortfolioManager()

    @pytest.fixture
    def stock_config(self):
        return PortfolioConfig(
            name="Test Stock Portfolio",
            portfolio_type=PortfolioType.STOCK,
            base_currency=Currency.CNY,
            initial_capital=1_000_000,
            target_return_annual=0.15,
            risk_budget_annual=0.20,
        )

    def test_create_portfolio(self, manager, stock_config):
        portfolio = manager.create_portfolio(stock_config)
        assert portfolio.portfolio_id is not None
        assert portfolio.config.name == "Test Stock Portfolio"
        assert portfolio.status == PortfolioStatus.CREATED
        assert portfolio.record is not None
        assert portfolio.record.nav == 1_000_000

    def test_activate_portfolio(self, manager, stock_config):
        portfolio = manager.create_portfolio(stock_config)
        assert manager.activate_portfolio(portfolio.portfolio_id)
        p = manager.get_portfolio(portfolio.portfolio_id)
        assert p.status == PortfolioStatus.ACTIVE

    def test_list_portfolios(self, manager):
        configs = [
            PortfolioConfig(name="Stock A", portfolio_type=PortfolioType.STOCK, initial_capital=1000000),
            PortfolioConfig(name="ETF A", portfolio_type=PortfolioType.ETF, initial_capital=500000),
            PortfolioConfig(name="CTA A", portfolio_type=PortfolioType.CTA, initial_capital=2000000),
        ]
        for c in configs:
            manager.create_portfolio(c)

        all_p = manager.list_portfolios()
        assert len(all_p) == 3

        stock_p = manager.list_portfolios(portfolio_type=PortfolioType.STOCK)
        assert len(stock_p) == 1
        assert stock_p[0].config.name == "Stock A"

    def test_pause_and_close_portfolio(self, manager, stock_config):
        portfolio = manager.create_portfolio(stock_config)
        manager.activate_portfolio(portfolio.portfolio_id)

        assert manager.pause_portfolio(portfolio.portfolio_id)
        p = manager.get_portfolio(portfolio.portfolio_id)
        assert p.status == PortfolioStatus.PAUSED

        assert manager.close_portfolio(portfolio.portfolio_id)
        p = manager.get_portfolio(portfolio.portfolio_id)
        assert p.status == PortfolioStatus.CLOSED

    def test_add_position(self, manager, stock_config):
        portfolio = manager.create_portfolio(stock_config)
        manager.activate_portfolio(portfolio.portfolio_id)

        position = PositionRecord(
            symbol="000001.SZ",
            asset_class=AssetClass.EQUITY,
            quantity=10000,
            avg_cost=15.0,
            current_price=16.5,
            market_value=165000,
            weight=0.15,
            sector="Financials",
        )
        result = manager.add_position(portfolio.portfolio_id, position)
        assert result is not None
        positions = manager.get_positions(portfolio.portfolio_id)
        assert len(positions) == 1
        assert positions[0].symbol == "000001.SZ"

    def test_allocation_tree(self, manager):
        tree = manager.create_allocation_tree("Main Fund", 100_000_000)

        # Add fund nodes
        equity = manager.add_allocation_node(
            tree.root_id, "Equity Fund", AllocationType.FUND, 50.0,
            parent_id=tree.root_id, target_return=0.15, risk_budget=0.20,
        )
        assert equity is not None
        assert equity.allocated_capital == 50_000_000

        alt = manager.add_allocation_node(
            tree.root_id, "Alternative Fund", AllocationType.FUND, 30.0,
            parent_id=tree.root_id, target_return=0.20, risk_budget=0.25,
        )
        assert alt is not None

        # Add portfolio under equity
        stock_p = manager.add_allocation_node(
            tree.root_id, "Stock Portfolio", AllocationType.PORTFOLIO, 60.0,
            parent_id=equity.node_id, target_return=0.18, risk_budget=0.15,
        )
        assert stock_p is not None
        assert stock_p.allocated_capital == 30_000_000

        # Validate tree
        retrieved = manager.get_allocation_tree(tree.root_id)
        assert retrieved is not None
        assert len(retrieved.nodes) == 4

    def test_group_management(self, manager):
        configs = [
            PortfolioConfig(name="P1", portfolio_type=PortfolioType.STOCK, initial_capital=1000000),
            PortfolioConfig(name="P2", portfolio_type=PortfolioType.ETF, initial_capital=500000),
        ]
        ids = []
        for c in configs:
            p = manager.create_portfolio(c)
            manager.activate_portfolio(p.portfolio_id)
            ids.append(p.portfolio_id)

        group = manager.create_group("Test Group", ids)
        assert len(group.portfolios) == 2
        assert group.portfolios[0].parent_fund_id == group.group_id

        metrics = group.get_aggregate_metrics()
        assert metrics["portfolio_count"] == 2
        assert metrics["total_nav"] == 1_500_000

    def test_get_summary(self, manager, stock_config):
        manager.create_portfolio(stock_config)
        summary = manager.get_summary()
        assert summary["total_portfolios"] == 1
        assert summary["total_aum"] == 1_000_000

    def test_sector_exposure(self, manager, stock_config):
        portfolio = manager.create_portfolio(stock_config)
        manager.activate_portfolio(portfolio.portfolio_id)

        positions = [
            PositionRecord(symbol="S1", sector="Financials", market_value=300000, weight=0.3),
            PositionRecord(symbol="S2", sector="Tech", market_value=400000, weight=0.4),
            PositionRecord(symbol="S3", sector="Financials", market_value=200000, weight=0.2),
        ]
        for pos in positions:
            manager.add_position(portfolio.portfolio_id, pos)

        exposure = manager.get_sector_exposure_all()
        assert "Financials" in exposure
        assert "Tech" in exposure
