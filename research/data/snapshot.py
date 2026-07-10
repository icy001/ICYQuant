from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from .bar import Bar


@dataclass(frozen=True)
class MarketSnapshot:
    timestamp: datetime
    bars: Dict[str, Bar]

    def get(self, symbol: str) -> Optional[Bar]:
        return self.bars.get(symbol)

    def symbols(self) -> list[str]:
        return list(self.bars.keys())

    def __len__(self) -> int:
        return len(self.bars)