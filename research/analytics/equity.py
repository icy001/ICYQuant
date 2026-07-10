from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass(frozen=True)
class EquityPoint:
    timestamp: datetime
    equity: float


class EquityCurve:

    def __init__(self):
        self.points: List[EquityPoint] = []

    def add(self, timestamp: datetime, equity: float) -> None:
        self.points.append(EquityPoint(timestamp, equity))

    def values(self) -> List[float]:
        return [p.equity for p in self.points]

    def timestamps(self) -> List[datetime]:
        return [p.timestamp for p in self.points]

    def __len__(self) -> int:
        return len(self.points)

    def __getitem__(self, index: int) -> EquityPoint:
        return self.points[index]