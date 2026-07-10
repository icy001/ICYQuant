import pytest
from datetime import datetime

from research.execution.order import Order, OrderStatus, Side, OrderType
from research.execution.broker import SimulatedBroker
from research.execution.matcher import MatchingEngine
from research.execution.execution_report import ExecutionReport
from research.data.snapshot import MarketSnapshot
from research.data.bar import Bar


class TestMatchingEngine:

    def test_market_order_buy(self):
        matcher = MatchingEngine(commission_rate=0.005, spread=0.10, slippage_rate=0.001)
        order = Order(symbol="NVDA", side=Side.BUY, quantity=1000, order_type=OrderType.MARKET)

        fill = matcher.match(order, 100.00)

        assert fill is not None
        assert fill.order_id == order.order_id
        assert fill.symbol == "NVDA"
        assert fill.quantity == 1000
        assert fill.fill_price > 100.00
        assert fill.commission == 5.0
        assert fill.slippage > 0

    def test_market_order_sell(self):
        matcher = MatchingEngine(commission_rate=0.005, spread=0.10, slippage_rate=0.001)
        order = Order(symbol="NVDA", side=Side.SELL, quantity=1000, order_type=OrderType.MARKET)

        fill = matcher.match(order, 100.00)

        assert fill is not None
        assert fill.fill_price < 100.00
        assert fill.commission == 5.0

    def test_limit_order_not_supported(self):
        matcher = MatchingEngine()
        order = Order(symbol="NVDA", side=Side.BUY, quantity=100, order_type=OrderType.LIMIT, price=90.00)

        fill = matcher.match(order, 100.00)

        assert fill is None


class TestBroker:

    def test_market_order_fill(self):
        broker = SimulatedBroker()
        order = Order(symbol="NVDA", side=Side.BUY, quantity=100, order_type=OrderType.MARKET)
        ts = datetime.utcnow()

        snapshot = MarketSnapshot(
            timestamp=ts,
            bars={"NVDA": Bar(symbol="NVDA", timestamp=ts, open=100.00, high=101.00, low=99.00, close=100.00, volume=10000)}
        )

        report = broker.execute(order, snapshot)

        assert isinstance(report, ExecutionReport)
        assert report.order.status == OrderStatus.FILLED
        assert len(report.fills) == 1
        assert report.message == "Order filled successfully"

    def test_buy_order_price_adjustment(self):
        broker = SimulatedBroker(commission_rate=0.005, spread=0.10, slippage_rate=0.001)
        order = Order(symbol="NVDA", side=Side.BUY, quantity=1000, order_type=OrderType.MARKET)
        ts = datetime.utcnow()

        snapshot = MarketSnapshot(
            timestamp=ts,
            bars={"NVDA": Bar(symbol="NVDA", timestamp=ts, open=100.00, high=101.00, low=99.00, close=100.00, volume=10000)}
        )

        report = broker.execute(order, snapshot)

        fill = report.fills[0]
        expected_price = 100.00 + 0.05
        expected_price = expected_price * 1.001
        assert fill.fill_price == pytest.approx(expected_price, abs=0.001)

    def test_sell_order_price_adjustment(self):
        broker = SimulatedBroker(commission_rate=0.005, spread=0.10, slippage_rate=0.001)
        order = Order(symbol="NVDA", side=Side.SELL, quantity=1000, order_type=OrderType.MARKET)
        ts = datetime.utcnow()

        snapshot = MarketSnapshot(
            timestamp=ts,
            bars={"NVDA": Bar(symbol="NVDA", timestamp=ts, open=100.00, high=101.00, low=99.00, close=100.00, volume=10000)}
        )

        report = broker.execute(order, snapshot)

        fill = report.fills[0]
        expected_price = 100.00 - 0.05
        expected_price = expected_price * 0.999
        assert fill.fill_price == pytest.approx(expected_price, abs=0.001)

    def test_invalid_symbol_rejected(self):
        broker = SimulatedBroker()
        order = Order(symbol="INVALID", side=Side.BUY, quantity=100, order_type=OrderType.MARKET)
        ts = datetime.utcnow()

        snapshot = MarketSnapshot(
            timestamp=ts,
            bars={"NVDA": Bar(symbol="NVDA", timestamp=ts, open=100.00, high=101.00, low=99.00, close=100.00, volume=10000)}
        )

        report = broker.execute(order, snapshot)

        assert report.order.status == OrderStatus.REJECTED
        assert len(report.fills) == 0
        assert "not found" in report.message

    def test_get_order(self):
        broker = SimulatedBroker()
        order = Order(symbol="NVDA", side=Side.BUY, quantity=100, order_type=OrderType.MARKET)
        ts = datetime.utcnow()

        snapshot = MarketSnapshot(
            timestamp=ts,
            bars={"NVDA": Bar(symbol="NVDA", timestamp=ts, open=100.00, high=101.00, low=99.00, close=100.00, volume=10000)}
        )

        broker.execute(order, snapshot)

        retrieved_order = broker.get_order(str(order.order_id))
        assert retrieved_order is not None
        assert retrieved_order.order_id == order.order_id

    def test_get_all_orders(self):
        broker = SimulatedBroker()
        ts = datetime.utcnow()
        snapshot = MarketSnapshot(
            timestamp=ts,
            bars={"NVDA": Bar(symbol="NVDA", timestamp=ts, open=100.00, high=101.00, low=99.00, close=100.00, volume=10000)}
        )

        order1 = Order(symbol="NVDA", side=Side.BUY, quantity=100, order_type=OrderType.MARKET)
        order2 = Order(symbol="NVDA", side=Side.SELL, quantity=50, order_type=OrderType.MARKET)

        broker.execute(order1, snapshot)
        broker.execute(order2, snapshot)

        orders = broker.get_all_orders()
        assert len(orders) == 2


class TestOrder:

    def test_order_initial_status(self):
        order = Order(symbol="NVDA", side=Side.BUY, quantity=100)

        assert order.status == OrderStatus.NEW
        assert order.filled_quantity == 0.0

    def test_order_is_filled(self):
        order = Order(symbol="NVDA", side=Side.BUY, quantity=100)
        order.status = OrderStatus.FILLED

        assert order.is_filled() is True

    def test_order_is_active(self):
        order = Order(symbol="NVDA", side=Side.BUY, quantity=100)

        assert order.is_active() is True

        order.status = OrderStatus.FILLED
        assert order.is_active() is False


class TestExecutionReport:

    def test_execution_report_with_fills(self):
        order = Order(symbol="NVDA", side=Side.BUY, quantity=100)
        report = ExecutionReport(order=order, message="Test")

        assert report.order == order
        assert report.fills == []
        assert report.message == "Test"