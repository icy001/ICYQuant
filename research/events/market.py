from dataclasses import dataclass
from datetime import datetime

from research.data.snapshot import MarketSnapshot


@dataclass(frozen=True)
class MarketEvent:
    timestamp: datetime
    snapshot: MarketSnapshot