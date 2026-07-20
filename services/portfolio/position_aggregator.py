"""
Position aggregation engine.
"""

from decimal import Decimal

from .position_snapshot import PositionSnapshot


class PositionAggregator:
    def aggregate(
        self,
        positions,
        prices,
    ):
        result = {}

        for position in positions:
            if position.symbol not in result:
                result[position.symbol] = {
                    "quantity": Decimal("0"),
                    "cost": Decimal("0"),
                }

            result[position.symbol]["quantity"] += position.quantity
            result[position.symbol]["cost"] += position.quantity * position.average_price

        snapshots = []

        for symbol, value in result.items():
            quantity = value["quantity"]
            avg_price = value["cost"] / quantity

            snapshots.append(
                PositionSnapshot(
                    symbol=symbol,
                    quantity=quantity,
                    average_price=avg_price,
                    market_value=quantity * prices[symbol],
                )
            )

        return snapshots