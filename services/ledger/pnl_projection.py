from typing import Dict

from .event import LedgerEvent
from .event_type import LedgerEventType
from .projector import Projection


class PnLProjection(Projection):
    def __init__(self):
        self.state: Dict = {
            "prices": {},
            "positions": {},
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
            symbol = event.payload.get("symbol", "")
            side = event.payload.get("side", "")
            price = event.payload.get("price", 0.0)
            quantity = event.payload.get("quantity", 0.0)

            if symbol not in self.state["positions"]:
                self.state["positions"][symbol] = {"quantity": 0.0, "avg_cost": 0.0}

            current_qty = self.state["positions"][symbol]["quantity"]
            current_cost = self.state["positions"][symbol]["avg_cost"]

            if side == "BUY":
                new_qty = current_qty + quantity
                new_cost = ((current_qty * current_cost) + (quantity * price)) / new_qty if new_qty != 0 else 0.0
                self.state["positions"][symbol]["quantity"] = new_qty
                self.state["positions"][symbol]["avg_cost"] = new_cost
            else:
                sold_qty = min(quantity, current_qty) if current_qty > 0 else 0
                self.state["realized_pnl"] += (price - current_cost) * sold_qty
                self.state["daily_pnl"] += (price - current_cost) * sold_qty
                self.state["positions"][symbol]["quantity"] -= quantity
                if self.state["positions"][symbol]["quantity"] <= 0:
                    del self.state["positions"][symbol]

            self._calculate_unrealized_pnl()
        elif event.event_type == LedgerEventType.CASH_DEPOSITED:
            if self.state["initial_equity"] == 0:
                self.state["initial_equity"] = event.payload.get("amount", 0.0)

    def _calculate_unrealized_pnl(self) -> None:
        unrealized = 0.0
        for symbol, pos in self.state["positions"].items():
            price = self.state["prices"].get(symbol, pos["avg_cost"])
            unrealized += (price - pos["avg_cost"]) * pos["quantity"]
        self.state["unrealized_pnl"] = unrealized

    def reset(self) -> None:
        self.state = {
            "prices": {},
            "positions": {},
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "daily_pnl": 0.0,
            "initial_equity": 0.0
        }