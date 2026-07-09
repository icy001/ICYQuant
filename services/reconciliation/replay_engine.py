from typing import Any, List

from .snapshot_engine import PositionSnapshot


class ReplayEngine:
    def replay(
        self,
        events: list,
    ) -> float:
        quantity = 0.0

        for event in events:
            if event["type"] == "BUY":
                quantity += event["quantity"]
            elif event["type"] == "SELL":
                quantity -= event["quantity"]

        return quantity

    def rebuild(
        self,
        snapshot: PositionSnapshot,
        events: List[Any],
    ) -> float:
        position = snapshot.quantity

        for event in events:
            position = event.apply(position)

        return position
