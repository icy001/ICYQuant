from typing import Dict

from .event import LedgerEvent
from .event_type import LedgerEventType
from .projector import Projection


class CashProjection(Projection):
    def __init__(self):
        self.state: Dict[str, float] = {"cash": 0.0}

    @property
    def cash(self) -> float:
        return self.state.get("cash", 0.0)

    def apply(self, event: LedgerEvent) -> None:
        if event.event_type == LedgerEventType.CASH_DEPOSITED:
            self.state["cash"] += event.payload.get("amount", 0.0)
        elif event.event_type == LedgerEventType.CASH_WITHDRAWN:
            self.state["cash"] -= event.payload.get("amount", 0.0)
        elif event.event_type == LedgerEventType.ORDER_FILLED:
            self.state["cash"] += event.payload.get("cash_change", 0.0)
        elif event.event_type == LedgerEventType.COMMISSION_CHARGED:
            self.state["cash"] -= event.payload.get("amount", 0.0)
        elif event.event_type == LedgerEventType.DIVIDEND_RECEIVED:
            self.state["cash"] += event.payload.get("amount", 0.0)
        elif event.event_type == LedgerEventType.FEE_CHARGED:
            self.state["cash"] -= event.payload.get("amount", 0.0)
        elif event.event_type == LedgerEventType.SYSTEM_ADJUSTMENT:
            self.state["cash"] += event.payload.get("amount", 0.0)

    def reset(self) -> None:
        self.state = {"cash": 0.0}