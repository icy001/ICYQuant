from typing import Dict, List, Iterator, Tuple
from datetime import datetime

from research.data.bar import Bar


class Timeline:
    def __init__(self):
        self._timestamps: List[datetime] = []
        self._market_data: Dict[datetime, Dict[str, Bar]] = {}

    def merge(self, datasets: Dict[str, List[Bar]]) -> None:
        all_timestamps = set()
        
        for symbol, bars in datasets.items():
            for bar in bars:
                all_timestamps.add(bar.timestamp)
        
        self._timestamps = sorted(all_timestamps)
        
        for timestamp in self._timestamps:
            snapshot = {}
            for symbol, bars in datasets.items():
                for bar in bars:
                    if bar.timestamp == timestamp:
                        snapshot[symbol] = bar
                        break
            self._market_data[timestamp] = snapshot

    def get_snapshot(self, timestamp: datetime) -> Dict[str, Bar]:
        return self._market_data.get(timestamp, {})

    def __iter__(self) -> Iterator[Tuple[datetime, Dict[str, Bar]]]:
        for timestamp in self._timestamps:
            yield timestamp, self._market_data[timestamp]

    def __len__(self) -> int:
        return len(self._timestamps)