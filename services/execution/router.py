from typing import Dict

from services.trading.mode import TradingMode

from .adapters.base import BaseAdapter


class ExecutionRouter:
    def __init__(self, adapters: Dict[str, BaseAdapter]):
        self.adapters = adapters

    def route(self, order, mode: TradingMode = TradingMode.PAPER):
        adapter = self.adapters.get(mode.value)
        if adapter:
            return adapter.send_order(order)
        raise ValueError(f"No adapter registered for mode: {mode}")

    def register_adapter(self, mode: str, adapter: BaseAdapter) -> None:
        self.adapters[mode] = adapter