from dataclasses import dataclass


@dataclass
class PositionSnapshot:
    symbol: str
    quantity: float


class SnapshotEngine:
    def create(
        self,
        symbol: str,
        quantity: float,
    ) -> PositionSnapshot:
        return PositionSnapshot(
            symbol=symbol,
            quantity=quantity,
        )
