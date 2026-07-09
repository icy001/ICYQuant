from typing import Dict

from ..models import Fill

from .base import BaseAdapter


class IBKRAdapter(BaseAdapter):
    def __init__(self, host: str = "localhost", port: int = 4002, client_id: int = 1):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connected = False
        self._ib = None

    def connect(self) -> bool:
        try:
            self._ib = self._create_connection()
            self.connected = True
            return True
        except Exception:
            return False

    def disconnect(self) -> None:
        if self._ib:
            try:
                self._ib.disconnect()
            except Exception:
                pass
        self.connected = False

    def send_order(self, order):
        if not self.connected:
            return None

        fill = Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            quantity=order.quantity,
            price=order.price,
        )
        return fill

    def cancel_order(self, order_id: str) -> bool:
        return True

    def get_positions(self) -> Dict:
        return {}

    def get_account(self) -> Dict:
        return {
            "cash": 0.0,
            "positions": {},
            "connected": self.connected,
        }

    def _create_connection(self):
        return None