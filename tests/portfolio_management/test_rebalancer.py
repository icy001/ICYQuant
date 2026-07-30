"""Tests for Portfolio Rebalancer."""

import pytest
from services.portfolio_management.rebalancer import (
    PortfolioRebalancer, RebalanceConfig, RebalanceMethod,
    TargetWeight, Trade, TradeList, RebalanceResult,
)


class TestPortfolioRebalancer:
    """Test portfolio rebalancer."""

    @pytest.fixture
    def rebalancer(self):
        config = RebalanceConfig(
            method=RebalanceMethod.THRESHOLD,
            drift_threshold_pct=5.0,
            min_trade_value=1000,
        )
        return PortfolioRebalancer(config)

    @pytest.fixture
    def sample_weights(self):
        current = {
            "AAPL": 0.25,
            "GOOGL": 0.20,
            "MSFT": 0.15,
            "TSLA": 0.10,
            "AMZN": 0.10,
            "CASH": 0.20,
        }
        target = {
            "AAPL": 0.20,
            "GOOGL": 0.20,
            "MSFT": 0.20,
            "TSLA": 0.15,
            "AMZN": 0.15,
            "CASH": 0.10,
        }
        return current, target

    def test_compute_drift(self, rebalancer, sample_weights):
        current, target = sample_weights
        targets = rebalancer.compute_drift(current, target)

        assert len(targets) >= len(set(list(current.keys()) + list(target.keys())))

        # AAPL is over 5pp (25% -> 20%)
        aapl = next(t for t in targets if t.symbol == "AAPL")
        assert aapl.drift > 0  # overweight → positive drift (needs SELL)

        # TSLA underweight 5pp (10% -> 15%)
        tsla = next(t for t in targets if t.symbol == "TSLA")
        assert tsla.drift < 0  # underweight → negative drift (needs BUY)

    def test_should_rebalance_threshold(self, rebalancer, sample_weights):
        current, target = sample_weights
        targets = rebalancer.compute_drift(current, target)

        triggered, reason = rebalancer.should_rebalance(targets, last_rebalance_time=0)
        assert triggered
        assert "Threshold" in reason

    def test_should_not_rebalance_if_no_drift(self, rebalancer):
        weights = {"A": 0.3, "B": 0.3, "C": 0.4}
        targets = rebalancer.compute_drift(weights, weights)

        # No positions require trade
        triggered, reason = rebalancer.should_rebalance(targets)
        assert not triggered

    def test_generate_trades(self, rebalancer, sample_weights):
        current, target = sample_weights
        targets = rebalancer.compute_drift(current, target)
        nav = 1_000_000
        prices = {"AAPL": 180, "GOOGL": 140, "MSFT": 350, "TSLA": 250, "AMZN": 180, "CASH": 1}

        trade_list = rebalancer.generate_trades("port-1", targets, nav, prices)
        assert trade_list.trade_count > 0

        # Check buy/sell balance
        buys = trade_list.get_buys()
        sells = trade_list.get_sells()
        assert len(buys) >= 1
        assert len(sells) >= 1

    def test_full_rebalance_workflow(self, rebalancer, sample_weights):
        current, target = sample_weights
        nav = 1_000_000
        prices = {"AAPL": 180, "GOOGL": 140, "MSFT": 350, "TSLA": 250, "AMZN": 180, "CASH": 1}

        result = rebalancer.rebalance("port-1", current, target, nav, prices)
        assert result.triggered
        assert result.trade_list is not None
        assert len(result.trade_list.trades) > 0
        assert result.positions_rebalanced > 0

    def test_no_rebalance_when_in_alignment(self, rebalancer):
        weights = {"A": 0.30, "B": 0.30, "C": 0.40}
        nav = 1_000_000
        prices = {"A": 100, "B": 100, "C": 100}

        result = rebalancer.rebalance("port-1", weights, weights, nav, prices)
        assert not result.triggered

    def test_target_weight_properties(self):
        tw = TargetWeight(
            symbol="AAPL",
            current_weight=0.25,
            target_weight=0.20,
            drift=5.0,
            requires_trade=True,
        )
        assert tw.trade_direction == "SELL"
        assert tw.abs_drift == 5.0

    def test_trade_list_properties(self, rebalancer, sample_weights):
        current, target = sample_weights
        targets = rebalancer.compute_drift(current, target)
        nav = 1_000_000
        prices = {"AAPL": 180, "GOOGL": 140, "MSFT": 350, "TSLA": 250, "AMZN": 180, "CASH": 1}

        trade_list = rebalancer.generate_trades("port-1", targets, nav, prices)

        assert trade_list.total_buy_value > 0
        assert trade_list.total_sell_value > 0
        assert trade_list.estimated_total_cost >= 0
        assert trade_list.trade_count > 0

    def test_get_results(self, rebalancer, sample_weights):
        current, target = sample_weights
        nav = 1_000_000
        prices = {"AAPL": 180, "GOOGL": 140, "MSFT": 350, "TSLA": 250, "AMZN": 180, "CASH": 1}

        rebalancer.rebalance("port-1", current, target, nav, prices)
        results = rebalancer.get_results()
        assert len(results) == 1

        port_results = rebalancer.get_results(portfolio_id="port-1")
        assert len(port_results) == 1

    def test_summary(self, rebalancer, sample_weights):
        current, target = sample_weights
        nav = 1_000_000
        prices = {"AAPL": 180, "GOOGL": 140, "MSFT": 350, "TSLA": 250, "AMZN": 180, "CASH": 1}

        rebalancer.rebalance("port-1", current, target, nav, prices)
        summary = rebalancer.get_summary()
        assert summary["total_rebalances"] >= 1
        assert summary["method"] == "threshold"
