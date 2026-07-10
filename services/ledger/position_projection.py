from typing import Dict

from .projector import Projection
from .event import LedgerEvent, LedgerEventType


class PositionProjection(Projection):
    def __init__(self):
        self.state: Dict[str, Dict] = {}

    def get_position(self, symbol: str) -> Dict:
        return self.state.get(symbol, {"quantity": 0.0, "avg_cost": 0.0})

    def apply(self, event: LedgerEvent) -> None:
        if event.event_type == LedgerEventType.ORDER_FILLED:
            symbol = event.payload.get("symbol", "")
            side = event.payload.get("side", "")
            price = event.payload.get("price", 0.0)
            quantity = event.payload.get("quantity", 0.0)

            if symbol not in self.state:
                self.state[symbol] = {"quantity": 0.0, "avg_cost": 0.0}

            current_qty = self.state[symbol]["quantity"]
            current_cost = self.state[symbol]["avg_cost"]

            if side == "BUY":
                new_qty = current_qty + quantity
                new_cost = ((current_qty * current_cost) + (quantity * price)) / new_qty if new_qty != 0 else 0.0
            else:
                new_qty = current_qty - quantity
                new_cost = current_cost

            self.state[symbol]["quantity"] = new_qty
            self.state[symbol]["avg_cost"] = new_cost

            if new_qty == 0:
                del self.state[symbol]

        elif event.event_type == LedgerEventType.POSITION_OPENED:
            symbol = event.payload.get("symbol", "")
            self.state[symbol] = {
                "quantity": event.payload.get("quantity", 0.0),
                "avg_cost": event.payload.get("avg_cost", 0.0)
            }

        elif event.event_type == LedgerEventType.POSITION_CLOSED:
            symbol = event.payload.get("symbol", "")
            if symbol in self.state:
                del self.state[symbol]

    def reset(self) -> None:
        self.state = {}