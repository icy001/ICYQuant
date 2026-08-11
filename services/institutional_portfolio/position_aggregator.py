"""
Position Aggregator — Aggregate Strategy Positions to Portfolio Level

Rolls up all strategy-level positions into portfolio-level positions.
Outputs: gross exposure, net exposure, long/short exposure, leverage.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AggregatedPosition:
    asset: str
    total: float = 0.0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    strategy_count: int = 0


class PositionAggregator:
    """
    Aggregates per-strategy positions into portfolio-level positions.
    Computes: gross, net, long, short exposures with strategy count.
    """

    def __init__(
        self,
        agg_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.agg_id = agg_id or f"pa-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._positions: Dict[str, AggregatedPosition] = {}

    def aggregate(self, strategy_positions: Dict[str, Dict[str, float]]) -> Dict[str, AggregatedPosition]:
        self._positions.clear()
        asset_map: Dict[str, Dict] = {}

        for sid, positions in strategy_positions.items():
            for asset, pos in positions.items():
                entry = asset_map.setdefault(asset, {"total": 0.0, "long": 0.0, "short": 0.0, "count": 0})
                entry["total"] += pos
                entry["count"] += 1
                if pos > 0:
                    entry["long"] += pos
                else:
                    entry["short"] += abs(pos)

        for asset, data in asset_map.items():
            self._positions[asset] = AggregatedPosition(
                asset=asset,
                total=data["total"],
                long_exposure=data["long"],
                short_exposure=data["short"],
                strategy_count=data["count"],
            )

        return self._positions

    def get_gross(self) -> float:
        return sum(p.long_exposure + p.short_exposure for p in self._positions.values())

    def get_net(self) -> float:
        return sum(p.total for p in self._positions.values())

    def get_long_exposure(self) -> float:
        return sum(p.long_exposure for p in self._positions.values())

    def get_short_exposure(self) -> float:
        return sum(p.short_exposure for p in self._positions.values())

    def get_leverage(self) -> float:
        net = self.get_net()
        gross = self.get_gross()
        return gross / abs(net) if net != 0 else 1.0

    def get_summary(self) -> Dict[str, Any]:
        return {
            "agg_id": self.agg_id,
            "positions": len(self._positions),
            "gross": self.get_gross(),
            "net": self.get_net(),
            "long": self.get_long_exposure(),
            "short": self.get_short_exposure(),
            "leverage": self.get_leverage(),
        }
