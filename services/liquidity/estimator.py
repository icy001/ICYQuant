"""Market Estimator — Bid/Ask Imbalance & Execution Guidance.

Analyzes bid/ask imbalance in the order book to determine:
- Market directional pressure (buy vs sell)
- Recommended execution aggressiveness
- Urgency adjustment for execution algorithms

Guides the Execution Optimizer based on real-time microstructure.
"""

from __future__ import annotations

from typing import Optional

from .models import (
    ImbalanceAnalysis,
    MarketCondition,
    OrderBook,
    Side,
)


class ImbalanceEstimator:
    """Analyzes bid/ask pressure and provides execution guidance.

    Detects order book imbalances and translates them into
    actionable execution parameters for the optimizer.

    Usage:
        estimator = ImbalanceEstimator()
        analysis = estimator.analyze(book)
        print(f"Condition: {analysis.condition.value}")
        print(f"Aggressiveness: {analysis.suggested_aggressiveness}")
    """

    def __init__(self) -> None:
        pass

    def analyze(self, book: OrderBook) -> ImbalanceAnalysis:
        """Analyze bid/ask imbalance in the order book.

        Computes the balance of buying vs selling pressure and
        derives execution recommendations.

        Args:
            book: OrderBook to analyze

        Returns:
            ImbalanceAnalysis with pressure assessment and guidance
        """
        imbalance = book.imbalance_ratio

        # Component metrics
        bid_vol = book.total_bid_volume
        ask_vol = book.total_ask_volume
        bid_depth_5 = book.bid_depth_5
        ask_depth_5 = book.ask_depth_5

        # Weighted prices
        w_bid = book.weighted_bid_price
        w_ask = book.weighted_ask_price

        # Derive execution guidance
        aggressiveness, urgency, note = self._derive_guidance(
            imbalance, book, bid_vol, ask_vol
        )

        return ImbalanceAnalysis(
            symbol=book.symbol,
            imbalance_ratio=imbalance,
            bid_volume=bid_vol,
            ask_volume=ask_vol,
            bid_depth_5=bid_depth_5,
            ask_depth_5=ask_depth_5,
            weighted_bid=w_bid,
            weighted_ask=w_ask,
            suggested_aggressiveness=aggressiveness,
            suggested_urgency=urgency,
            note=note,
        )

    def _derive_guidance(
        self,
        imbalance: float,
        book: OrderBook,
        bid_vol: float,
        ask_vol: float,
    ) -> tuple:
        """Derive execution guidance from imbalance.

        Returns:
            Tuple of (aggressiveness, urgency, note)
        """
        if imbalance >= 0.8:
            return (
                0.90, "HIGH",
                f"Strong buy pressure. Bid volume ({bid_vol:.0f}) >> Ask ({ask_vol:.0f}). "
                "Consider waiting for pullback or using limit orders for sells."
            )
        elif imbalance >= 0.65:
            return (
                0.70, "NORMAL",
                f"Buy pressure. Bid volume ({bid_vol:.0f}) > Ask ({ask_vol:.0f}). "
                "Slightly favorable for sells, use moderate aggression for buys."
            )
        elif imbalance <= 0.2:
            return (
                0.90, "HIGH",
                f"Strong sell pressure. Ask volume ({ask_vol:.0f}) >> Bid ({bid_vol:.0f}). "
                "Consider waiting for bounce or using limit orders for buys."
            )
        elif imbalance <= 0.35:
            return (
                0.70, "NORMAL",
                f"Sell pressure. Ask volume ({ask_vol:.0f}) > Bid ({bid_vol:.0f}). "
                "Slightly favorable for buys, use moderate aggression for sells."
            )
        else:
            return (
                0.50, "NORMAL",
                f"Balanced market. Bid ({bid_vol:.0f}) ≈ Ask ({ask_vol:.0f}). "
                "Normal execution conditions."
            )

    def get_execution_recommendation(
        self,
        book: OrderBook,
        side: Side,
        quantity: float,
    ) -> dict:
        """Get complete execution recommendation based on imbalance.

        Combines imbalance analysis with order details to recommend
        execution parameters.

        Args:
            book: OrderBook
            side: BUY or SELL
            quantity: Order quantity

        Returns:
            Execution recommendation dict
        """
        analysis = self.analyze(book)

        # Adjust aggression based on side
        # BUY into sell pressure = less aggressive
        # SELL into buy pressure = less aggressive
        aggression = analysis.suggested_aggressiveness

        if side == Side.BUY:
            if analysis.condition in (MarketCondition.EXTREME_BUY, MarketCondition.BUY_PRESSURE):
                aggression = min(aggression - 0.2, 0.3)
                urgency = "LOW"
                algo = "TWAP"
            elif analysis.condition in (MarketCondition.EXTREME_SELL, MarketCondition.SELL_PRESSURE):
                aggression = min(aggression + 0.1, 1.0)
                urgency = "HIGH"
                algo = "POV"
            else:
                urgency = "NORMAL"
                algo = "VWAP"
        else:  # SELL
            if analysis.condition in (MarketCondition.EXTREME_SELL, MarketCondition.SELL_PRESSURE):
                aggression = min(aggression - 0.2, 0.3)
                urgency = "LOW"
                algo = "TWAP"
            elif analysis.condition in (MarketCondition.EXTREME_BUY, MarketCondition.BUY_PRESSURE):
                aggression = min(aggression + 0.1, 1.0)
                urgency = "HIGH"
                algo = "POV"
            else:
                urgency = "NORMAL"
                algo = "VWAP"

        return {
            "symbol": book.symbol,
            "side": side.value,
            "quantity": quantity,
            "condition": analysis.condition.value,
            "imbalance_ratio": round(analysis.imbalance_ratio, 4),
            "recommended_algorithm": algo,
            "aggressiveness": round(aggression, 2),
            "urgency": urgency,
            "note": analysis.note,
        }
