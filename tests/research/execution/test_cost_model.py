import pytest

from research.execution.commission import PerShareCommission
from research.execution.spread import FixedSpread
from research.execution.slippage import PercentageSlippage
from research.execution.cost import TransactionCost
from research.backtest.order import Order


class TestCommission:

    def test_per_share_commission_buy(self):
        model = PerShareCommission(0.005)
        cost = model.calculate(1000)
        assert cost == 5.0

    def test_per_share_commission_sell(self):
        model = PerShareCommission(0.005)
        cost = model.calculate(-1000)
        assert cost == 5.0

    def test_per_share_commission_custom_rate(self):
        model = PerShareCommission(0.01)
        cost = model.calculate(500)
        assert cost == 5.0


class TestSpread:

    def test_fixed_spread_buy(self):
        spread = FixedSpread(0.10)
        adjusted = spread.adjust_price(100.00, "BUY")
        assert adjusted == 100.05

    def test_fixed_spread_sell(self):
        spread = FixedSpread(0.10)
        adjusted = spread.adjust_price(100.00, "SELL")
        assert adjusted == 99.95

    def test_fixed_spread_larger_spread(self):
        spread = FixedSpread(0.20)
        buy_price = spread.adjust_price(100.00, "BUY")
        sell_price = spread.adjust_price(100.00, "SELL")
        assert buy_price == 100.10
        assert sell_price == 99.90


class TestSlippage:

    def test_percentage_slippage_buy(self):
        slippage = PercentageSlippage(0.0005)
        adjusted = slippage.adjust(100.00, "BUY")
        assert adjusted == pytest.approx(100.05)

    def test_percentage_slippage_sell(self):
        slippage = PercentageSlippage(0.0005)
        adjusted = slippage.adjust(100.00, "SELL")
        assert adjusted == pytest.approx(99.95)

    def test_percentage_slippage_higher_rate(self):
        slippage = PercentageSlippage(0.001)
        buy_price = slippage.adjust(200.00, "BUY")
        sell_price = slippage.adjust(200.00, "SELL")
        assert buy_price == pytest.approx(200.20)
        assert sell_price == pytest.approx(199.80)


class TestTransactionCost:

    def test_transaction_cost_buy(self):
        commission = PerShareCommission(0.005)
        spread = FixedSpread(0.10)
        slippage = PercentageSlippage(0.0005)

        cost_model = TransactionCost(commission, spread, slippage)

        order = Order(
            order_id="1",
            symbol="NVDA",
            side="BUY",
            quantity=1000
        )

        result = cost_model.calculate(order, 100.00)

        assert result["cost"] == 5.0
        assert result["price"] == pytest.approx(100.10005, abs=0.0001)

    def test_transaction_cost_sell(self):
        commission = PerShareCommission(0.005)
        spread = FixedSpread(0.10)
        slippage = PercentageSlippage(0.0005)

        cost_model = TransactionCost(commission, spread, slippage)

        order = Order(
            order_id="1",
            symbol="NVDA",
            side="SELL",
            quantity=-1000
        )

        result = cost_model.calculate(order, 100.00)

        assert result["cost"] == 5.0
        assert result["price"] == pytest.approx(99.89995, abs=0.0001)

    def test_transaction_cost_aggregation(self):
        commission = PerShareCommission(0.01)
        spread = FixedSpread(0.20)
        slippage = PercentageSlippage(0.001)

        cost_model = TransactionCost(commission, spread, slippage)

        order = Order(
            order_id="2",
            symbol="GLD",
            side="BUY",
            quantity=500
        )

        result = cost_model.calculate(order, 300.00)

        assert result["cost"] == 5.0
        assert result["price"] == pytest.approx(300.4001, abs=0.0001)