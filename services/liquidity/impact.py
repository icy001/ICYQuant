"""Market Impact Engine.

Predicts the market impact of an order using microstructure data.

Models:
- Temporary Impact: transient price pressure from order execution
- Permanent Impact: lasting price dislocation from information content

Combines with spread cost for total execution cost estimate.

Uses order book depth to refine impact estimates beyond
simple participation-based models.
"""

from __future__ import annotations

import math
from typing import Optional

from .models import (
    LiquidityGrade,
    MarketImpactEstimate,
    OrderBook,
    Side,
)


# =============================================================================
# Market Impact Engine
# =============================================================================


class MarketImpactEngine:
    """Predicts market impact using order book and market data.

    Combines microstructure-based temporary impact with
    participation-based permanent impact.

    Temporary Impact:
        η · σ · (Q_t / ADV_T)^β   where Q_t is per-slice quantity

    Permanent Impact:
        γ · σ · (Q_total / ADV)^γ  where Q_total is full order

    Usage:
        engine = MarketImpactEngine()
        estimate = engine.estimate(
            book=order_book,
            quantity=100000,
            side=Side.BUY,
            volatility=0.25,
        )
        print(f"Expected impact: {estimate.total_impact_pct:.2%}")
    """

    def __init__(
        self,
        temporary_impact_factor: float = 0.15,
        permanent_impact_factor: float = 0.10,
        beta: float = 0.6,
        gamma: float = 0.5,
    ) -> None:
        """Initialize impact engine.

        Args:
            temporary_impact_factor: η — temporary impact coefficient
            permanent_impact_factor: γ — permanent impact coefficient
            beta: Temporary impact exponent (typ 0.5-0.7)
            gamma: Permanent impact exponent (typ 0.5)
        """
        self.eta = temporary_impact_factor
        self.gamma_val = permanent_impact_factor
        self.beta = beta
        self.gamma_exp = gamma

    def estimate(
        self,
        book: OrderBook,
        quantity: float,
        side: Side = Side.BUY,
        volatility: float = 0.25,
        time_fraction: float = 1.0,
        num_slices: int = 1,
    ) -> MarketImpactEstimate:
        """Estimate the market impact of an order.

        Args:
            book: Current order book
            quantity: Order quantity
            side: BUY or SELL
            volatility: Annualized volatility (default 0.25 = 25%)
            time_fraction: Fraction of trading day available
            num_slices: Number of slices to split order into

        Returns:
            MarketImpactEstimate with impact prediction
        """
        adv = max(book.adv, book.daily_volume)
        if adv <= 0:
            adv = book.total_bid_volume + book.total_ask_volume
            if adv <= 0:
                adv = 1_000_000  # Default 1M shares

        # Participation rate
        participation = quantity / adv if adv > 0 else 0.0

        # Per-slice quantity
        slice_qty = quantity / num_slices
        slice_time = time_fraction / num_slices if num_slices > 1 else time_fraction

        # Temporary impact (per slice, dissipates)
        if slice_time > 0 and adv > 0:
            temp_impact = self.eta * volatility * (slice_qty / (adv * slice_time)) ** self.beta
        else:
            temp_impact = 0.0

        # Permanent impact (total, persists)
        if adv > 0:
            perm_impact = self.gamma_val * volatility * (quantity / adv) ** self.gamma_exp
        else:
            perm_impact = 0.0

        # Spread cost (half-spread)
        spread_cost = book.spread_bps / 2.0

        # Convert impacts to bps
        temp_impact_bps = temp_impact * 10000
        perm_impact_bps = perm_impact * 10000

        total_impact_bps = temp_impact_bps + perm_impact_bps
        expected_slippage_bps = total_impact_bps + spread_cost
        total_cost_bps = expected_slippage_bps

        # Recommendation
        recommended_slices, recommended_algo = self._recommend(
            participation, book, quantity, volatility
        )
        if num_slices > 1:
            recommended_slices = num_slices

        # Confidence based on data quality
        confidence = self._estimate_confidence(book, adv, volatility)

        return MarketImpactEstimate(
            symbol=book.symbol,
            order_quantity=quantity,
            order_side=side,
            temporary_impact_bps=temp_impact_bps,
            permanent_impact_bps=perm_impact_bps,
            total_impact_bps=total_impact_bps,
            total_impact_pct=total_impact_bps / 10000.0,
            spread_cost_bps=spread_cost,
            expected_slippage_bps=expected_slippage_bps,
            total_cost_bps=total_cost_bps,
            participation_rate=participation,
            recommended_slices=recommended_slices,
            recommended_algorithm=recommended_algo,
            confidence=confidence,
            spread_bps=book.spread_bps,
            adv=adv,
            volatility=volatility,
        )

    # -------------------------------------------------------------------------
    # Algorithm Recommendation
    # -------------------------------------------------------------------------

    def _recommend(
        self,
        participation: float,
        book: OrderBook,
        quantity: float,
        volatility: float,
    ) -> tuple:
        """Recommend slicing and algorithm based on conditions.

        Returns:
            Tuple of (recommended_slices, recommended_algorithm_name)
        """
        # Low participation = simple execution
        if participation <= 0.01:  # < 1%
            return 1, "DIRECT"
        elif participation <= 0.05:  # 1-5%
            return 1, "TWAP"

        # Medium participation = moderate slicing
        elif participation <= 0.10:  # 5-10%
            if volatility > 0.40:
                return 5, "POV"
            else:
                return 5, "VWAP"

        # High participation = aggressive slicing
        elif participation <= 0.20:  # 10-20%
            return 10, "POV"

        # Very high participation = maximum caution
        else:
            slices = min(int(participation * 100), 30)
            return max(10, slices), "POV_AGGRESSIVE"

    def _estimate_confidence(
        self,
        book: OrderBook,
        adv: float,
        volatility: float,
    ) -> float:
        """Estimate confidence in the impact prediction.

        Higher confidence when order book data is rich and vol is low.

        Args:
            book: OrderBook
            adv: Average daily volume
            volatility: Annualized volatility

        Returns:
            Confidence score 0.0 - 1.0
        """
        confidence = 0.5  # Base

        # More levels = more confidence
        if book.level_count >= 10:
            confidence += 0.15
        elif book.level_count >= 5:
            confidence += 0.10

        # High volume confirmation
        if adv > 1_000_000:
            confidence += 0.10

        # Spread quality
        if book.spread_bps <= 2:
            confidence += 0.10
        elif book.spread_bps <= 10:
            confidence += 0.05

        # Volatility penalty
        if volatility > 0.5:
            confidence -= 0.10
        elif volatility > 0.3:
            confidence -= 0.05

        return max(0.1, min(0.99, confidence))

    # -------------------------------------------------------------------------
    # Impact Comparison
    # -------------------------------------------------------------------------

    def compare_algorithms(
        self,
        book: OrderBook,
        quantity: float,
        side: Side = Side.BUY,
        volatility: float = 0.25,
    ) -> dict:
        """Compare impact across different execution strategies.

        Args:
            book: Current order book
            quantity: Order quantity
            side: BUY or SELL
            volatility: Annualized volatility

        Returns:
            Dictionary comparing impact per algorithm
        """
        scenarios = [
            ("DIRECT", 1, 0.01),     # Single order, 1% of day
            ("TWAP_10", 10, 1.0),    # 10 slices, full day
            ("VWAP_26", 26, 1.0),    # 26 slices (30-min each), full day
            ("POV_30", 30, 1.0),     # 30 slices, full day
            ("POV_60", 60, 1.0),     # 60 slices, full day
        ]

        results = []
        for name, slices, time_frac in scenarios:
            est = self.estimate(
                book=book,
                quantity=quantity,
                side=side,
                volatility=volatility,
                time_fraction=time_frac,
                num_slices=slices,
            )
            results.append({
                "algorithm": name,
                "slices": slices,
                "total_impact_bps": round(est.total_impact_bps, 2),
                "total_cost_bps": round(est.total_cost_bps, 2),
                "impact_grade": est.impact_grade.value,
            })

        return {
            "symbol": book.symbol,
            "quantity": quantity,
            "scenarios": results,
            "best": min(results, key=lambda r: r["total_cost_bps"]),
        }

    # -------------------------------------------------------------------------
    # Depth-Aware Impact (uses order book levels directly)
    # -------------------------------------------------------------------------

    def estimate_from_depth(
        self,
        book: OrderBook,
        quantity: float,
        side: Side = Side.BUY,
    ) -> MarketImpactEstimate:
        """Estimate impact by walking the order book.

        More accurate than formula-based estimates for small/medium
        orders since it uses actual order book levels.

        Args:
            book: Current order book
            quantity: Order quantity
            side: BUY or SELL

        Returns:
            MarketImpactEstimate with depth-based prediction
        """
        mid = book.mid_price
        if mid <= 0:
            return self.estimate(book, quantity, side)

        remaining = quantity
        total_cost = 0.0
        filled_volume = 0.0

        levels = book.asks if side == Side.BUY else book.bids

        for level in levels:
            if remaining <= 0:
                break
            fill_qty = min(remaining, level.volume)
            total_cost += fill_qty * level.price
            filled_volume += fill_qty
            remaining -= fill_qty

        if filled_volume <= 0:
            return self.estimate(book, quantity, side)

        avg_exec_price = total_cost / filled_volume
        impact_bps = ((avg_exec_price - mid) / mid) * 10000

        # Adjust sign for SELL side
        if side == Side.SELL:
            impact_bps = abs(impact_bps)

        # Remaining unfilled = additional impact estimate
        if remaining > 0:
            extra_impact = self.estimate(book, remaining, side, num_slices=1)
            impact_bps += extra_impact.total_impact_bps

        spread_cost = book.spread_bps / 2.0
        total_cost_bps = impact_bps + spread_cost

        return MarketImpactEstimate(
            symbol=book.symbol,
            order_quantity=quantity,
            order_side=side,
            total_impact_bps=impact_bps,
            total_impact_pct=impact_bps / 10000.0,
            spread_cost_bps=spread_cost,
            expected_slippage_bps=total_cost_bps,
            total_cost_bps=total_cost_bps,
            participation_rate=quantity / max(book.adv, 1),
            spread_bps=book.spread_bps,
            adv=book.adv,
            confidence=0.85 if filled_volume >= quantity else 0.6,
        )
