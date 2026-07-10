from typing import Dict

from .projector import Projection
from .event import LedgerEvent, LedgerEventType


class PnLProjection(Projection):
    def __init__(self):
        self.state: Dict = {
            "prices": {},
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "daily_pnl": 0.0,
            "initial_equity": 0.0
        }

    @property
    def unrealized_pnl(self) -> float:
        return self.state.get("unrealized_pnl", 0.0)

    @property
    def realized_pnl(self) -> float:
        return self.state.get("realized_pnl", 0.0)

    def apply(self, event: LedgerEvent) -> None:
        if event.event_type == LedgerEventType.MARKET_PRICE_UPDATED:
            symbol = event.payload.get("symbol", "")
            price = event.payload.get("price", 0.0)
            self.state["prices"][symbol] = price
            self._calculate_unrealized_pnl()
        elif event.event_type == LedgerEventType.ORDER_FILLED:
            side = event.payload.get("side", "")
            price = event.payload.get("price", 0.0)
            quantity = event.payload.get("quantity", 0.0)
            avg_cost = event.payload.get("avg_cost", 0.0)

            if side == "SELL":
                self.state["realized_pnl"] += (price - avg_cost) * quantity
                self.state["daily_pnl"] += (price - avg_cost) * quantity
        elif event.event_type == LedgerEventType.DEPOSIT:
            if self.state["initial_equity"] == 0:
                self.state["initial_equity"] = event.payload.get("amount", 0.0)

    def _calculate_unrealized_pnl(self) -> None:
        self.state["unrealized_pnl"] = 0.0

    def reset(self) -> None:
        self.state = {
            "prices": {},
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "daily_pnl": 0.0,
            "initial_equity": 0.0
        }