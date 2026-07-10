import pytest

from services.ledger.event import LedgerEvent
from services.ledger.event_type import LedgerEventType
from services.ledger.cash_projection import CashProjection
from services.ledger.position_projection import PositionProjection
from services.ledger.pnl_projection import PnLProjection


class TestCashProjection:

    def test_deposit(self):
        projection = CashProjection()
        event = LedgerEvent(event_type=LedgerEventType.CASH_DEPOSITED, payload={"amount": 100000.0})

        projection.apply(event)

        assert projection.cash == 100000.0

    def test_buy_order_filled(self):
        projection = CashProjection()
        projection.state["cash"] = 100000.0
        event = LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"side": "BUY", "price": 100.0, "quantity": 100, "cash_change": -10000.0})

        projection.apply(event)

        assert projection.cash == 90000.0

    def test_sell_order_filled(self):
        projection = CashProjection()
        projection.state["cash"] = 90000.0
        event = LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"side": "SELL", "price": 110.0, "quantity": 100, "cash_change": 11000.0})

        projection.apply(event)

        assert projection.cash == 101000.0

    def test_commission_charged(self):
        projection = CashProjection()
        projection.state["cash"] = 100000.0
        event = LedgerEvent(event_type=LedgerEventType.COMMISSION_CHARGED, payload={"amount": 5.0})

        projection.apply(event)

        assert projection.cash == 99995.0

    def test_reset(self):
        projection = CashProjection()
        projection.state["cash"] = 50000.0

        projection.reset()

        assert projection.cash == 0.0


class TestPositionProjection:

    def test_buy_position(self):
        projection = PositionProjection()
        event = LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "NVDA", "side": "BUY", "price": 100.0, "quantity": 100})

        projection.apply(event)

        position = projection.get_position("NVDA")
        assert position["quantity"] == 100
        assert position["avg_cost"] == 100.0

    def test_sell_position(self):
        projection = PositionProjection()
        projection.state["NVDA"] = {"quantity": 100, "avg_cost": 100.0}
        event = LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "NVDA", "side": "SELL", "price": 110.0, "quantity": 50})

        projection.apply(event)

        position = projection.get_position("NVDA")
        assert position["quantity"] == 50
        assert position["avg_cost"] == 100.0

    def test_close_position(self):
        projection = PositionProjection()
        projection.state["NVDA"] = {"quantity": 50, "avg_cost": 100.0}
        event = LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "NVDA", "side": "SELL", "price": 110.0, "quantity": 50})

        projection.apply(event)

        assert "NVDA" not in projection.state

    def test_reset(self):
        projection = PositionProjection()
        projection.state["NVDA"] = {"quantity": 100, "avg_cost": 100.0}

        projection.reset()

        assert projection.state == {}


class TestPnLProjection:

    def test_price_update(self):
        projection = PnLProjection()
        event = LedgerEvent(event_type=LedgerEventType.MARKET_PRICE_UPDATED, payload={"symbol": "NVDA", "price": 105.0})

        projection.apply(event)

        assert projection.state["prices"]["NVDA"] == 105.0

    def test_sell_realized_pnl(self):
        projection = PnLProjection()
        projection.state["positions"]["NVDA"] = {"quantity": 100, "avg_cost": 100.0}
        event = LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "NVDA", "side": "SELL", "price": 110.0, "quantity": 100})

        projection.apply(event)

        assert projection.realized_pnl == 1000.0

    def test_deposit_initial_equity(self):
        projection = PnLProjection()
        event = LedgerEvent(event_type=LedgerEventType.CASH_DEPOSITED, payload={"amount": 100000.0})

        projection.apply(event)

        assert projection.state["initial_equity"] == 100000.0