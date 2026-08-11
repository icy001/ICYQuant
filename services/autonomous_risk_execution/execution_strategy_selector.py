"""
Execution Strategy Selector — selects optimal execution algorithm per order.

Considers:
    - Order size vs ADV
    - Bid/ask spread
    - Volatility
    - Urgency (alpha decay)
    - Market impact estimate
    - Liquidity profile
    - Historical strategy performance
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class StrategyScore:
    """Score for a single execution strategy."""
    strategy: str
    cost_score: float = 0.0
    speed_score: float = 0.0
    certainty_score: float = 0.0
    impact_score: float = 0.0
    total_score: float = 0.0


@dataclass
class StrategySelection:
    """Strategy selection result."""
    id: str = field(default_factory=lambda: str(uuid4()))
    order_id: str = ""
    selected_strategy: str = "VWAP"
    scores: list[StrategyScore] = field(default_factory=list)
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class ExecutionStrategySelector:
    """
    Selects the optimal execution strategy based on market conditions.

    Strategy selection is adaptive:
        - Low spread → MARKET or LIMIT
        - Normal conditions → TWAP or VWAP
        - Large order / low liquidity → ICEBERG or POV
        - High volatility → ADAPTIVE
        - High urgency → MARKET or ADAPTIVE
    """

    # Strategy characteristics: (cost_friendliness, speed, certainty, impact_control)
    STRATEGY_PROFILES = {
        "MARKET": (0.30, 1.00, 1.00, 0.20),
        "LIMIT": (0.90, 0.30, 0.40, 0.80),
        "TWAP": (0.70, 0.50, 0.70, 0.60),
        "VWAP": (0.75, 0.50, 0.70, 0.65),
        "POV": (0.65, 0.60, 0.75, 0.75),
        "ADAPTIVE": (0.60, 0.70, 0.60, 0.70),
        "LIQUIDITY_SEEKING": (0.50, 0.40, 0.50, 0.85),
        "ICEBERG": (0.55, 0.45, 0.65, 0.90),
        "IMPLEMENTATION_SHORTFALL": (0.70, 0.55, 0.60, 0.70),
    }

    def __init__(self) -> None:
        self._selection_history: list[StrategySelection] = []

    async def select(
        self,
        order_id: str,
        quantity: int,
        adv: float,
        spread_bps: float = 5.0,
        volatility: float = 0.15,
        urgency: str = "MEDIUM",
        expected_impact_bps: Optional[float] = None,
    ) -> StrategySelection:
        """
        Select the best execution strategy.

        Decision factors:
            - Size/ADV ratio → larger = more careful execution needed
            - Spread → wider = more limit-oriented
            - Volatility → higher = more adaptive
            - Urgency → higher = more aggressive
            - Expected impact → higher = more control needed
        """
        result = StrategySelection(order_id=order_id)
        pct_adv = abs(quantity) / max(adv, 1)

        # Compute feature weights
        size_weight = min(1.0, pct_adv / 0.10)  # 0-1, normalized to 10% ADV
        spread_weight = min(1.0, spread_bps / 30.0)
        vol_weight = min(1.0, volatility / 0.50)
        urgency_weight = {"CRITICAL": 1.0, "HIGH": 0.7, "MEDIUM": 0.4, "LOW": 0.1}.get(urgency, 0.4)

        scores = []
        for strategy, (cost, speed, certainty, impact) in self.STRATEGY_PROFILES.items():
            # Weighted score based on current conditions
            total = (
                cost * (1 - urgency_weight) * 0.30  # Cost matters less when urgent
                + speed * urgency_weight * 0.25  # Speed matters more when urgent
                + certainty * (1 - vol_weight) * 0.15  # Certainty less valuable in high vol
                + impact * size_weight * 0.30  # Impact control matters more for large orders
            )
            scores.append(StrategyScore(
                strategy=strategy,
                cost_score=cost,
                speed_score=speed,
                certainty_score=certainty,
                impact_score=impact,
                total_score=total,
            ))

        # Sort by total score
        scores.sort(key=lambda s: s.total_score, reverse=True)
        result.scores = scores
        result.selected_strategy = scores[0].strategy

        # Reason
        top = scores[0]
        second = scores[1] if len(scores) > 1 else top
        result.reason = (
            f"Selected {top.strategy} (score={top.total_score:.2f}) over "
            f"{second.strategy} (score={second.total_score:.2f}) | "
            f"PctADV={pct_adv:.1%} Urgency={urgency} Vol={volatility:.0%}"
        )

        result.timestamp = datetime.now()
        self._selection_history.append(result)
        if len(self._selection_history) > 500:
            self._selection_history = self._selection_history[-250:]

        logger.debug("Strategy selection: %s", result.reason)
        return result

    async def get_recommendations(
        self, order: dict, market: dict
    ) -> list[tuple[str, float]]:
        """Get ranked strategy recommendations."""
        sel = await self.select(
            order.get("id", ""),
            order.get("quantity", 0),
            market.get("adv", 1_000_000),
            market.get("spread_bps", 5),
            market.get("volatility", 0.15),
            order.get("urgency", "MEDIUM"),
        )
        return [(s.strategy, s.total_score) for s in sel.scores]

    @property
    def selection_history(self) -> list[StrategySelection]:
        return self._selection_history[-100:]
