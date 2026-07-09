from typing import Dict

from services.trading.mode import TradingMode

from .adapters.base import BaseAdapter
from .adapters.paper import PaperAdapter


class ExecutionGateway:
    def __init__(self, adapters: Dict[str, BaseAdapter] = None):
        self.adapters = adapters or {}
        if TradingMode.PAPER.value not in self.adapters:
            self.adapters[TradingMode.PAPER.value] = PaperAdapter()

    def register_adapter(self, mode: str, adapter: BaseAdapter) -> None:
        self.adapters[mode] = adapter

    def get_adapter(self, mode: str) -> BaseAdapter:
        return self.adapters.get(mode)

    def connect(self, mode: str = None) -> bool:
        adapter = self.get_adapter(mode or TradingMode.PAPER.value)
        if adapter:
            return adapter.connect()
        return False

    def disconnect(self, mode: str = None) -> None:
        adapter = self.get_adapter(mode or TradingMode.PAPER.value)
        if adapter:
            adapter.disconnect()

    def send_order(self, order, mode: str = None):
        adapter = self.get_adapter(mode or TradingMode.PAPER.value)
        if adapter:
            return adapter.send_order(order)
        return None

    def cancel_order(self, order_id: str, mode: str = None) -> bool:
        adapter = self.get_adapter(mode or TradingMode.PAPER.value)
        if adapter:
            return adapter.cancel_order(order_id)
        return False

    def get_positions(self, mode: str = None) -> Dict:
        adapter = self.get_adapter(mode or TradingMode.PAPER.value)
        if adapter:
            return adapter.get_positions()
        return {}

    def get_account(self, mode: str = None) -> Dict:
        adapter = self.get_adapter(mode or TradingMode.PAPER.value)
        if adapter:
            return adapter.get_account()
        return {}