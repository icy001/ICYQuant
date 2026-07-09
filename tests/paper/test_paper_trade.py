import pytest

from services.execution.adapters.paper import PaperAdapter
from services.execution.gateway import ExecutionGateway
from services.oms.models import Order
from services.trading.mode import TradingMode


class TestPaperTrade:
    def test_paper_adapter_connect(self):
        adapter = PaperAdapter()
        assert adapter.connect() is True
        assert adapter.connected is True

    def test_paper_adapter_send_buy_order(self):
        adapter = PaperAdapter()
        adapter.connect()

        order = Order(symbol="NVDA", side="BUY", quantity=100, price=480.0)
        fill = adapter.send_order(order)

        assert fill is not None
        assert fill.order_id == order.order_id
        assert fill.symbol == "NVDA"
        assert fill.quantity == 100
        assert fill.price == 480.0

        positions = adapter.get_positions()
        assert positions["NVDA"] == 100

        account = adapter.get_account()
        assert account["cash"] == 1000000.0 - (100 * 480.0)

    def test_paper_adapter_send_sell_order(self):
        adapter = PaperAdapter()
        adapter.connect()
        adapter._positions["NVDA"] = 200

        order = Order(symbol="NVDA", side="SELL", quantity=100, price=480.0)
        fill = adapter.send_order(order)

        assert fill is not None
        positions = adapter.get_positions()
        assert positions["NVDA"] == 100

    def test_paper_adapter_cancel_order(self):
        adapter = PaperAdapter()
        adapter.connect()

        order = Order(symbol="NVDA", side="BUY", quantity=100, price=480.0)
        adapter.send_order(order)

        assert adapter.cancel_order(order.order_id) is True
        assert adapter.cancel_order("non-existent") is False

    def test_execution_gateway_with_paper(self):
        gateway = ExecutionGateway()
        assert gateway.connect(TradingMode.PAPER.value) is True

        order = Order(symbol="NVDA", side="BUY", quantity=50, price=480.0)
        fill = gateway.send_order(order, TradingMode.PAPER.value)

        assert fill is not None
        assert gateway.get_positions(TradingMode.PAPER.value)["NVDA"] == 50