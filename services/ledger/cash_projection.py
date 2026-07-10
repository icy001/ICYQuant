from typing import Dict

from .projector import Projection
from .event import LedgerEvent, LedgerEventType


class CashProjection(Projection):
    def __init__(self):
        self.state: Dict[str, float] = {"cash": 0.0}

    @property
    def cash(self) -> float:
        return self.state.get("cash", 0.0)

    def apply(self, event: LedgerEvent) -> None:
        if event.event_type == LedgerEventType.DEPOSIT:
            self.state["cash"] += event.payload.get("amount", 0.0)
        elif event.event_type == LedgerEventType.WITHDRAWAL:
            self.state["cash"] -= event.payload.get("amount", 0.0)
        elif event.event_type == LedgerEventType.ORDER_FILLED:
            side = event.payload.get("side", "")
            price = event.payload.get("price", 0.0)
            quantity = event.payload.get("quantity", 0.0)
            if side == "BUY":
                self.state["cash"] -= price * quantity
            else:
                self.state["cash"] += price * quantity
        elif event.event_type == LedgerEventType.COMMISSION_CHARGED:
            self.state["cash"] -= event.payload.get("amount", 0.0)
        elif event.event_type == LedgerEventType.DIVIDEND_RECEIVED:
            self.state["cash"] += event.payload.get("amount", 0.0)
        elif event.event_type == LedgerEventType.CASH_ADJUSTED:
            self.state["cash"] += event.payload.get("adjustment", 0.0)

    def reset(self) -> None:
        self.state = {"cash": 0.0}