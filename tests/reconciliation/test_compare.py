import pytest

from services.reconciliation.compare.cash_comparator import CashComparator
from services.reconciliation.compare.order_comparator import OrderComparator
from services.reconciliation.compare.position_comparator import PositionComparator
from services.reconciliation.compare.trade_comparator import TradeComparator
from services.contracts.dto import OrderDTO, TradeDTO


class TestPositionComparator:
    def test_compare_with_matching_positions(self):
        comparator = PositionComparator()
        expected = {"AAPL": 100.0, "GOOGL": 50.0}
        actual = {"AAPL": 100.0, "GOOGL": 50.0}
        result = comparator.compare(expected, actual)
        assert len(result) == 0

    def test_compare_with_differences(self):
        comparator = PositionComparator()
        expected = {"AAPL": 100.0, "GOOGL": 50.0}
        actual = {"AAPL": 99.0, "GOOGL": 51.0}
        result = comparator.compare(expected, actual)
        assert len(result) == 2


class TestCashComparator:
    def test_compare_with_matching_balances(self):
        comparator = CashComparator()
        expected = {"user1": 1000.0, "user2": 2000.0}
        actual = {"user1": 1000.0, "user2": 2000.0}
        result = comparator.compare(expected, actual)
        assert len(result) == 0


class TestTradeComparator:
    def test_compare_with_matching_trades(self):
        comparator = TradeComparator()
        expected = [TradeDTO(trade_id="t1", user_id="u1", symbol="AAPL", price=100.0, quantity=10.0)]
        actual = [TradeDTO(trade_id="t1", user_id="u1", symbol="AAPL", price=100.0, quantity=10.0)]
        result = comparator.compare(expected, actual)
        assert len(result) == 0


class TestOrderComparator:
    def test_compare_with_matching_orders(self):
        comparator = OrderComparator()
        expected = [OrderDTO(order_id="o1", user_id="u1", symbol="AAPL", side="BUY", quantity=10.0, status="FILLED")]
        actual = [OrderDTO(order_id="o1", user_id="u1", symbol="AAPL", side="BUY", quantity=10.0, status="FILLED")]
        result = comparator.compare(expected, actual)
        assert len(result) == 0
