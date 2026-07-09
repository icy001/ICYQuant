import pytest

from services.execution.adapters.ibkr import IBKRAdapter
from services.execution.adapters.mt5 import MT5Adapter
from services.execution.adapters.ctp import CTPAdapter
from services.oms.models import Order


class TestIBKRAdapter:
    def test_ibkr_adapter_connect(self):
        adapter = IBKRAdapter()
        assert adapter.connect() is True
        assert adapter.connected is True

    def test_ibkr_adapter_send_order(self):
        adapter = IBKRAdapter()
        adapter.connect()

        order = Order(symbol="NVDA", side="BUY", quantity=100, price=480.0)
        fill = adapter.send_order(order)

        assert fill is not None
        assert fill.order_id == order.order_id

    def test_ibkr_adapter_disconnect(self):
        adapter = IBKRAdapter()
        adapter.connect()
        adapter.disconnect()
        assert adapter.connected is False


class TestMT5Adapter:
    def test_mt5_adapter_connect(self):
        adapter = MT5Adapter()
        assert adapter.connect() is True

    def test_mt5_adapter_send_order(self):
        adapter = MT5Adapter()
        adapter.connect()

        order = Order(symbol="EURUSD", side="BUY", quantity=0.1, price=1.08)
        fill = adapter.send_order(order)

        assert fill is not None

    def test_mt5_adapter_close_position(self):
        adapter = MT5Adapter()
        assert adapter.close_position("pos123") is True


class TestCTPAdapter:
    def test_ctp_adapter_connect(self):
        adapter = CTPAdapter()
        assert adapter.connect() is True

    def test_ctp_adapter_send_order(self):
        adapter = CTPAdapter()
        adapter.connect()

        order = Order(symbol="AU2106", side="BUY", quantity=1, price=370.0)
        fill = adapter.send_order(order)

        assert fill is not None