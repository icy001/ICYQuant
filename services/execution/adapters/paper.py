import time
from typing import Dict

from ..models import Fill

from .base import BaseAdapter


class PaperAdapter(BaseAdapter):
    def __init__(self, latency_ms: int = 100):
        self.connected = False
        self.latency_ms = latency_ms
        self._positions: Dict[str, float] = {}
        self._cash = 1000000.0
        self._filled_orders = {}

    def connect(self) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> None:
        self.connected = False

    def send_order(self, order):
        if not self.connected:
            return None

        time.sleep(self.latency_ms / 1000.0)

        fill = Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            quantity=order.quantity,
            price=order.price,
        )

        self._filled_orders[order.order_id] = fill

        if order.side == "BUY":
            self._positions[order.symbol] = self._positions.get(order.symbol, 0) + order.quantity
            self._cash -= order.quantity * order.price
        else:
            self._positions[order.symbol] = self._positions.get(order.symbol, 0) - order.quantity
            self._cash += order.quantity * order.price

        return fill

    def cancel_order(self, order_id: str) -> bool:
        if order_id in self._filled_orders:
            del self._filled_orders[order_id]
            return True
        return False

    def get_positions(self) -> Dict:
        return dict(self._positions)

    def get_account(self) -> Dict:
        return {
            "cash": self._cash,
            "positions": self._positions,
            "connected": self.connected,
        }