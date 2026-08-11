"""
Position Netting Engine — Cross-Strategy Position Cancellation

After signal netting, net positions across strategies:

    Strategy A = +10M NVDA
    Strategy B = +7M NVDA
    Strategy C = -6M NVDA
    ──────────────────────
    Net Position = +11M NVDA  (NOT 23M gross)

Institutional value: reduces gross turnover, commissions, spread, and impact.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class NettedPosition:
    asset: str
    net_position: float  # Final signed position
    gross_long: float
    gross_short: float
    strategy_contributions: Dict[str, float] = field(default_factory=dict)
    netting_savings_pct: float = 0.0


class PositionNettingEngine:
    """
    Nets positions across all strategies to minimize gross exposure.

    Key insight: Internal netting reduces unnecessary market orders.
    23M gross → 11M net means 52% reduction in turnover & costs.
    """

    def __init__(
        self,
        engine_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.engine_id = engine_id or f"pne-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._netted: Dict[str, NettedPosition] = {}
        self._strategy_positions: Dict[str, Dict[str, float]] = {}

    def set_strategy_positions(self, strategy_id: str, positions: Dict[str, float]) -> None:
        self._strategy_positions[strategy_id] = positions

    def net(self) -> Dict[str, NettedPosition]:
        """Net all strategy positions into unified portfolio positions."""
        self._netted.clear()
        asset_positions: Dict[str, Dict[str, float]] = {}

        for sid, positions in self._strategy_positions.items():
            for asset, pos in positions.items():
                asset_positions.setdefault(asset, {})[sid] = pos

        for asset, contributors in asset_positions.items():
            net = sum(contributors.values())
            gross_long = sum(v for v in contributors.values() if v > 0)
            gross_short = abs(sum(v for v in contributors.values() if v < 0))
            gross_total = gross_long + gross_short

            savings = 1.0 - (abs(net) / gross_total) if gross_total > 0 else 0.0

            self._netted[asset] = NettedPosition(
                asset=asset,
                net_position=net,
                gross_long=gross_long,
                gross_short=gross_short,
                strategy_contributions=contributors,
                netting_savings_pct=savings,
            )

        return self._netted

    def get_net_positions(self) -> Dict[str, float]:
        return {a: p.net_position for a, p in self._netted.items()}

    def get_gross_exposure(self) -> float:
        return sum(p.gross_long + p.gross_short for p in self._netted.values())

    def get_net_exposure(self) -> float:
        return sum(p.net_position for p in self._netted.values())

    def get_total_savings(self) -> float:
        gross = self.get_gross_exposure()
        net = abs(self.get_net_exposure())
        return 1.0 - (net / gross) if gross > 0 else 0.0

    def get_summary(self) -> Dict[str, Any]:
        return {
            "engine_id": self.engine_id,
            "positions": len(self._netted),
            "gross_exposure": self.get_gross_exposure(),
            "net_exposure": self.get_net_exposure(),
            "netting_savings_pct": self.get_total_savings(),
        }
