"""Liquidity Scoring Engine.

Computes a composite liquidity score (0-100) from:
- Depth Score: order book depth relative to order size
- Spread Score: bid-ask spread narrowness
- Turnover Score: daily trading volume
- Fill Probability: likelihood of execution

Scoring:
    90-100  EXCELLENT (A)
    70-90   GOOD      (B)
    50-70   NORMAL    (C)
    30-50   POOR      (D)
    0-30    AVOID     (F)
"""

from __future__ import annotations

import math
from typing import Optional

from .models import LiquidityGrade, LiquidityScore, OrderBook


class LiquidityScorer:
    """Computes composite liquidity scores from market data.

    Combines depth, spread, turnover, and fill probability
    into a single 0-100 score with grade classification.

    Usage:
        scorer = LiquidityScorer()
        score = scorer.score(book, order_quantity=50000)
        print(f"Liquidity: {score.score:.0f} - {score.grade.value}")
    """

    def __init__(self) -> None:
        # Component weights (sum to 1.0)
        self.depth_weight: float = 0.30
        self.spread_weight: float = 0.25
        self.turnover_weight: float = 0.25
        self.fill_probability_weight: float = 0.20

    def score(
        self,
        book: OrderBook,
        order_quantity: float = 0.0,
        volatility: float = 0.0,
    ) -> LiquidityScore:
        """Compute the composite liquidity score.

        Args:
            book: OrderBook to analyze
            order_quantity: Reference order size for depth assessment
            volatility: Annualized volatility (for fill probability)

        Returns:
            LiquidityScore with composite and component scores
        """
        # 1. Depth Score
        depth_score = self._score_depth(book, order_quantity)

        # 2. Spread Score
        spread_score = self._score_spread(book)

        # 3. Turnover Score
        turnover_score = self._score_turnover(book)

        # 4. Fill Probability
        fill_prob = self._estimate_fill_probability(book, order_quantity, volatility)

        # Composite weighted score
        composite = (
            self.depth_weight * depth_score
            + self.spread_weight * spread_score
            + self.turnover_weight * turnover_score
            + self.fill_probability_weight * fill_prob
        )

        best_vol = 0.0
        if order_quantity > 0:
            bb = book.best_bid
            ba = book.best_ask
            if bb and ba:
                best_vol = max(bb.volume, ba.volume) / order_quantity

        return LiquidityScore(
            symbol=book.symbol,
            score=min(100.0, composite),
            depth_score=min(100.0, depth_score),
            spread_score=min(100.0, spread_score),
            turnover_score=min(100.0, turnover_score),
            fill_probability=fill_prob,
            spread_bps=book.spread_bps,
            depth_at_best=best_vol,
            daily_volume=book.daily_volume,
            adv=book.adv,
            volatility=volatility,
        )

    # -------------------------------------------------------------------------
    # Component Scorers (each returns 0-100)
    # -------------------------------------------------------------------------

    def _score_depth(self, book: OrderBook, order_quantity: float) -> float:
        """Score based on how many multiples of order_quantity at the best price.

        Args:
            book: OrderBook
            order_quantity: Reference order size

        Returns:
            Depth score 0-100
        """
        bb = book.best_bid
        ba = book.best_ask
        if bb is None and ba is None:
            return 0.0

        best_vol = 0.0
        if bb:
            best_vol = max(best_vol, bb.volume)
        if ba:
            best_vol = max(best_vol, ba.volume)

        if order_quantity <= 0:
            return 50.0  # Neutral when no reference

        multiple = best_vol / order_quantity
        # Saturation curve: 0x -> 0, 10x -> 100
        if multiple >= 10:
            return 100.0
        elif multiple >= 5:
            return 85.0 + (multiple - 5) * 3.0
        elif multiple >= 1:
            return 50.0 + (multiple - 1) * 8.75
        else:
            return multiple * 50.0

    def _score_spread(self, book: OrderBook) -> float:
        """Score based on bid-ask spread tightness.

        Args:
            book: OrderBook

        Returns:
            Spread score 0-100
        """
        spread_bps = book.spread_bps
        if spread_bps <= 0:
            return 100.0

        # Very tight: <= 0.5 bps = 100
        # Wide: >= 100 bps = 0
        if spread_bps <= 0.5:
            return 100.0
        elif spread_bps >= 100:
            return 0.0
        else:
            # Logarithmic decay: tighter spreads score higher
            return 100.0 * (1.0 - math.log10(spread_bps) / 2.0)

    def _score_turnover(self, book: OrderBook) -> float:
        """Score based on daily trading volume.

        Args:
            book: OrderBook

        Returns:
            Turnover score 0-100
        """
        vol = max(book.daily_volume, book.adv)
        if vol <= 0:
            return 0.0

        # Saturation: 10M+ shares/day = 100
        if vol >= 10_000_000:
            return 100.0
        elif vol >= 1_000_000:
            return 60.0 + (vol - 1_000_000) / 9_000_000 * 40.0
        elif vol >= 100_000:
            return 30.0 + (vol - 100_000) / 900_000 * 30.0
        elif vol >= 10_000:
            return 10.0 + (vol - 10_000) / 90_000 * 20.0
        else:
            return vol / 10_000 * 10.0

    def _estimate_fill_probability(
        self,
        book: OrderBook,
        order_quantity: float,
        volatility: float,
    ) -> float:
        """Estimate probability of filling the order at/near current price.

        Higher depth + lower volatility = higher fill probability.

        Args:
            book: OrderBook
            order_quantity: Order size
            volatility: Annualized volatility

        Returns:
            Fill probability score 0-100
        """
        if order_quantity <= 0:
            return 100.0

        bb = book.best_bid
        ba = book.best_ask
        if bb is None and ba is None:
            return 0.0

        best_vol = 0.0
        if bb:
            best_vol = max(best_vol, bb.volume)
        if ba:
            best_vol = max(best_vol, ba.volume)

        # Base probability from depth coverage
        coverage = best_vol / order_quantity
        base_prob = min(100.0, coverage * 100.0)

        # Adjust for volatility (higher vol = lower fill certainty)
        if volatility > 0:
            vol_penalty = min(0.5, volatility * 0.5)
            base_prob *= (1.0 - vol_penalty)

        # Adjust for spread (wider spread = less certain)
        spread_bps = book.spread_bps
        if spread_bps > 0:
            spread_penalty = min(0.3, spread_bps / 200.0)
            base_prob *= (1.0 - spread_penalty)

        return min(100.0, base_prob)
