from typing import Dict

from ..models import Fill

from .base import BaseAdapter


class MT5Adapter(BaseAdapter):
    def __init__(self, server: str = "", login: int = 0, password: str = ""):
        self.server = server
        self.login = login
        self.password = password
        self.connected = False

    def connect(self) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> None:
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
            "equity": 0.0,
            "margin": 0.0,
            "positions": {},
            "connected": self.connected,
        }

    def close_position(self, position_id: str) -> bool:
        return True