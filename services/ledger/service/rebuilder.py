from typing import Dict, List

from ..event import LedgerEvent
from ..event_type import LedgerEventType


class PositionRebuilder:
    def rebuild(self, events: List[LedgerEvent]) -> Dict[str, float]:
        positions: Dict[str, float] = {}

        for event in events:
            if event.event_type == LedgerEventType.ORDER_FILLED:
                symbol = event.payload.get("symbol")
                side = event.payload.get("side", "")
                quantity = event.payload.get("quantity", 0.0)
                if symbol:
                    if symbol not in positions:
                        positions[symbol] = 0.0
                    if side == "BUY":
                        positions[symbol] += quantity
                    else:
                        positions[symbol] -= quantity

        return {k: v for k, v in positions.items() if v != 0}


class CashRebuilder:
    def rebuild(self, events: List[LedgerEvent]) -> float:
        cash = 0.0

        for event in events:
            if event.event_type == LedgerEventType.CASH_DEPOSITED:
                cash += event.payload.get("amount", 0.0)
            elif event.event_type == LedgerEventType.CASH_WITHDRAWN:
                cash -= event.payload.get("amount", 0.0)
            elif event.event_type == LedgerEventType.ORDER_FILLED:
                cash += event.payload.get("cash_change", 0.0)
            elif event.event_type == LedgerEventType.COMMISSION_CHARGED:
                cash -= event.payload.get("amount", 0.0)
            elif event.event_type == LedgerEventType.DIVIDEND_RECEIVED:
                cash += event.payload.get("amount", 0.0)
            elif event.event_type == LedgerEventType.FEE_CHARGED:
                cash -= event.payload.get("amount", 0.0)
            elif event.event_type == LedgerEventType.SYSTEM_ADJUSTMENT:
                cash += event.payload.get("amount", 0.0)

        return cash