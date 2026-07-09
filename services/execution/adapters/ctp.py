from typing import Dict

from ..models import Fill

from .base import BaseAdapter


class CTPAdapter(BaseAdapter):
    def __init__(
        self,
        front_address: str = "",
        broker_id: str = "",
        investor_id: str = "",
        password: str = "",
        app_id: str = "",
        auth_code: str = "",
    ):
        self.front_address = front_address
        self.broker_id = broker_id
        self.investor_id = investor_id
        self.password = password
        self.app_id = app_id
        self.auth_code = auth_code
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
            "positions": {},
            "available": 0.0,
            "frozen": 0.0,
            "connected": self.connected,
        }