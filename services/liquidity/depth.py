"""Market Depth Analyzer.

Analyzes order book depth to determine how much volume can be
executed at various price impact thresholds.

Assesses depth quality as: DEEP, MODERATE, SHALLOW, THIN
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .models import DepthAnalysis, DepthLevel, OrderBook


class DepthAnalyzer:
    """Analyzes order book depth for execution planning.

    Computes how much volume is available before price moves
    by specific amounts (5, 10, 25, 50 bps).

    Usage:
        analyzer = DepthAnalyzer()
        analysis = analyzer.analyze(book, order_quantity=50000)
        print(f"Depth: {analysis.level.value}, {analysis.depth_multiple}x")
    """

    def __init__(self) -> None:
        pass

    def analyze(
        self,
        book: OrderBook,
        order_quantity: float = 0.0,
    ) -> DepthAnalysis:
        """Analyze the order book depth.

        Args:
            book: OrderBook to analyze
            order_quantity: Reference order size for depth_multiple calculation

        Returns:
            DepthAnalysis with volume-at-threshold data
        """
        mid = book.mid_price
        if mid <= 0:
            return DepthAnalysis(symbol=book.symbol, level=DepthLevel.THIN)

        # Compute volumes at each impact threshold
        thresholds_bps = [5, 10, 25, 50]
        volumes_buy: Dict[int, float] = {}
        volumes_sell: Dict[int, float] = {}

        for t in thresholds_bps:
            target_move = mid * (t / 10000.0)
            volumes_buy[t] = self._volume_to_move(book.asks, mid, target_move)
            volumes_sell[t] = self._volume_to_move(book.bids, mid, target_move)

        # Depth multiple: how many multiples of order_quantity at best
        best_bid_vol = book.best_bid.volume if book.best_bid else 0.0
        best_ask_vol = book.best_ask.volume if book.best_ask else 0.0
        best_vol = max(best_bid_vol, best_ask_vol)
        depth_multiple = best_vol / order_quantity if order_quantity > 0 else 0.0

        return DepthAnalysis(
            symbol=book.symbol,
            volume_at_5bps=max(volumes_buy[5], volumes_sell[5]),
            volume_at_10bps=max(volumes_buy[10], volumes_sell[10]),
            volume_at_25bps=max(volumes_buy[25], volumes_sell[25]),
            volume_at_50bps=max(volumes_buy[50], volumes_sell[50]),
            depth_multiple=depth_multiple,
        )

    def _volume_to_move(
        self,
        levels: list,
        start_price: float,
        max_move: float,
    ) -> float:
        """Cumulative volume available within a price move.

        Args:
            levels: Sorted price levels (asks ascending or bids descending)
            start_price: Reference price
            max_move: Maximum acceptable price move

        Returns:
            Cumulative volume
        """
        total_vol = 0.0
        for level in levels:
            if level.price <= 0:
                continue
            move = abs(level.price - start_price)
            if move <= max_move:
                total_vol += level.volume
            else:
                break
        return total_vol

    def assess_depth_level(self, depth_multiple: float) -> DepthLevel:
        """Classify depth quality by multiple.

        Args:
            depth_multiple: How many multiples of order size at best price

        Returns:
            DepthLevel classification
        """
        if depth_multiple >= 50:
            return DepthLevel.DEEP
        elif depth_multiple >= 10:
            return DepthLevel.MODERATE
        elif depth_multiple >= 2:
            return DepthLevel.SHALLOW
        return DepthLevel.THIN

    def estimate_slices_needed(
        self,
        book: OrderBook,
        quantity: float,
        max_impact_bps: float = 5.0,
    ) -> int:
        """Estimate minimum slices needed to limit impact.

        Args:
            book: OrderBook
            quantity: Total order quantity
            max_impact_bps: Maximum acceptable impact per slice (bps)

        Returns:
            Recommended number of slices
        """
        mid = book.mid_price
        if mid <= 0:
            return max(1, int(quantity / 100))

        target_move = mid * (max_impact_bps / 10000.0)
        volume_per_slice = self._volume_to_move(book.asks, mid, target_move)

        if volume_per_slice <= 0:
            return max(1, int(quantity / 100))

        slices = int(quantity / volume_per_slice) + 1
        return max(1, min(slices, 50))  # Cap at 50 slices
