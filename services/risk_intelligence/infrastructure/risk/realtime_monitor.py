import time
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class MarketSnapshot:
    timestamp: int
    index_value: float
    index_change_pct: float
    vix_value: float
    volume_ratio: float
    bid_ask_spread: float
    volatility: float
    liquidity_score: float


class RealtimeRiskMonitor:
    def __init__(self, service=None):
        self.service = service
        self.snapshots: List[MarketSnapshot] = []
        self.max_history = 1000

    def record_snapshot(
        self,
        index_value: float = 4000.0,
        index_change_pct: float = 0.0,
        vix_value: float = 15.0,
        volume_ratio: float = 1.0,
        bid_ask_spread: float = 0.0005,
        volatility: float = 0.15,
        liquidity_score: float = 0.8,
    ) -> MarketSnapshot:
        snapshot = MarketSnapshot(
            timestamp=int(time.time()),
            index_value=index_value,
            index_change_pct=index_change_pct,
            vix_value=vix_value,
            volume_ratio=volume_ratio,
            bid_ask_spread=bid_ask_spread,
            volatility=volatility,
            liquidity_score=liquidity_score,
        )

        self.snapshots.append(snapshot)
        if len(self.snapshots) > self.max_history:
            self.snapshots = self.snapshots[-self.max_history:]

        return snapshot

    def get_latest_snapshot(self) -> Optional[MarketSnapshot]:
        return self.snapshots[-1] if self.snapshots else None

    def get_snapshot_range(
        self, count: int = 10
    ) -> List[MarketSnapshot]:
        return self.snapshots[-count:]

    def compute_trend(self, window: int = 10) -> float:
        if len(self.snapshots) < 2:
            return 0.0
        recent = self.snapshots[-window:]
        if len(recent) < 2:
            return 0.0
        first = recent[0].index_value
        last = recent[-1].index_value
        if first == 0:
            return 0.0
        return (last - first) / first

    def compute_volatility(self, window: int = 20) -> float:
        if len(self.snapshots) < window:
            return 0.15
        recent = self.snapshots[-window:]
        changes = []
        for i in range(1, len(recent)):
            prev = recent[i - 1].index_value
            if prev > 0:
                changes.append((recent[i].index_value - prev) / prev)
        if not changes:
            return 0.15
        mean = sum(changes) / len(changes)
        variance = sum((c - mean) ** 2 for c in changes) / len(changes)
        return variance ** 0.5

    def compute_volume_ratio(self, window: int = 20) -> float:
        if len(self.snapshots) < window:
            return 1.0
        recent = self.snapshots[-window:]
        avg_volume = sum(s.volume_ratio for s in recent) / len(recent)
        if avg_volume == 0:
            return 1.0
        return recent[-1].volume_ratio / avg_volume
