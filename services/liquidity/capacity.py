"""Strategy Capacity Analyzer.

Evaluates the maximum capital a trading strategy can manage before
significantly impacting market prices. Uses participation rate
constraints and order book depth to estimate capacity limits.

Key metrics:
- Max daily notional (subject to participation rate limit)
- Max single order size (subject to order book depth)
- Max position size (subject to ADV and liquidity)
- Current utilization vs capacity
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import (
    CapacityEstimate,
    CapacityLevel,
    OrderBook,
    PriceLevel,
)


class CapacityAnalyzer:
    """Analyzes strategy capacity constraints.

    Determines maximum fund size based on market liquidity
    and microstructure constraints.

    Usage:
        analyzer = CapacityAnalyzer(target_participation=0.10)
        capacity = analyzer.analyze(
            book=order_book,
            strategy_id="AI_Momentum",
            price=150.0,
            current_daily_notional=5_000_000,
            current_position=100000,
        )
        print(f"Capacity Level: {capacity.level.value}")
        print(f"Can scale: {capacity.can_scale}")
    """

    def __init__(
        self,
        target_participation: float = 0.10,
        max_turnover_ratio: float = 0.25,
        max_position_adv_multiple: float = 5.0,
    ) -> None:
        """Initialize capacity analyzer.

        Args:
            target_participation: Max participation rate (default 10%)
            max_turnover_ratio: Max daily turnover as fraction of ADV
            max_position_adv_multiple: Max position size as multiple of ADV
        """
        self.target_participation = target_participation
        self.max_turnover_ratio = max_turnover_ratio
        self.max_position_adv_multiple = max_position_adv_multiple

    def analyze(
        self,
        book: OrderBook,
        strategy_id: str,
        price: float = 0.0,
        current_daily_notional: float = 0.0,
        current_position: float = 0.0,
    ) -> CapacityEstimate:
        """Analyze strategy capacity.

        Args:
            book: Current order book
            strategy_id: Strategy identifier
            price: Current price (for notional calculations)
            current_daily_notional: Current daily trading notional
            current_position: Current position size in shares

        Returns:
            CapacityEstimate with limits and levels
        """
        if price <= 0:
            price = book.mid_price
        if price <= 0:
            price = 100.0  # Default fallback

        adv = max(book.adv, book.daily_volume)
        if adv <= 0:
            adv = 100_000  # Default 100k shares

        # Max daily notional: participation rate * ADV * price
        max_daily_shares = self.target_participation * adv
        max_daily_notional = max_daily_shares * price

        # Max single order: depth-safe execution size
        max_single_order = self._estimate_max_single_order(book)

        # Max position: position limit based on ADV
        max_position_size = self.max_position_adv_multiple * adv

        capacity = CapacityEstimate(
            strategy_id=strategy_id,
            symbol=book.symbol,
            max_daily_notional=max_daily_notional,
            max_single_order=max_single_order,
            max_position_size=max_position_size,
            current_daily_notional=current_daily_notional,
            current_position=current_position,
            adv=adv,
            target_participation=self.target_participation,
            price=price,
        )

        return capacity

    def _estimate_max_single_order(self, book: OrderBook) -> float:
        """Estimate maximum single order size from book depth.

        Considers volume at the best price level and total depth.

        Args:
            book: OrderBook

        Returns:
            Maximum safe single order size in shares
        """
        best_bid_vol = book.best_bid.volume if book.best_bid else 0.0
        best_ask_vol = book.best_ask.volume if book.best_ask else 0.0
        best_vol = max(best_bid_vol, best_ask_vol)

        # Use the smaller side (bid for buy orders, ask for sell)
        total_bid = book.total_bid_volume
        total_ask = book.total_ask_volume

        # Max single order = best level volume + 50% of remaining depth
        remaining_bid = max(0.0, total_bid - best_vol)
        remaining_ask = max(0.0, total_ask - best_vol)

        bid_capacity = best_vol + 0.5 * remaining_bid
        ask_capacity = best_vol + 0.5 * remaining_ask

        return max(bid_capacity, ask_capacity)

    def analyze_multi_symbol(
        self,
        books: Dict[str, OrderBook],
        strategy_id: str,
        prices: Optional[Dict[str, float]] = None,
        current_daily_notionals: Optional[Dict[str, float]] = None,
        current_positions: Optional[Dict[str, float]] = None,
    ) -> List[CapacityEstimate]:
        """Analyze capacity across multiple symbols.

        Args:
            books: Dictionary of symbol -> OrderBook
            strategy_id: Strategy identifier
            prices: Optional dict of symbol -> price
            current_daily_notionals: Optional dict of symbol -> daily notional
            current_positions: Optional dict of symbol -> position

        Returns:
            List of CapacityEstimate results per symbol
        """
        prices = prices or {}
        notionals = current_daily_notionals or {}
        positions = current_positions or {}

        results = []
        for symbol, book in books.items():
            result = self.analyze(
                book=book,
                strategy_id=strategy_id,
                price=prices.get(symbol, 0.0),
                current_daily_notional=notionals.get(symbol, 0.0),
                current_position=positions.get(symbol, 0.0),
            )
            results.append(result)
        return results

    def get_aggregate_capacity(
        self,
        estimates: List[CapacityEstimate],
    ) -> dict:
        """Aggregate capacity estimates across symbols.

        Args:
            estimates: List of per-symbol CapacityEstimate results

        Returns:
            Aggregated capacity summary
        """
        if not estimates:
            return {"total_max_daily": 0.0, "total_current_daily": 0.0,
                    "overall_level": CapacityLevel.HIGH.value}

        total_max = sum(e.max_daily_notional for e in estimates)
        total_current = sum(e.current_daily_notional for e in estimates)

        overall_pct = total_current / total_max if total_max > 0 else 0.0
        if overall_pct < 0.5:
            level = CapacityLevel.HIGH
        elif overall_pct < 1.0:
            level = CapacityLevel.ADEQUATE
        elif overall_pct < 2.0:
            level = CapacityLevel.CONSTRAINED
        else:
            level = CapacityLevel.LIMITED

        return {
            "strategy_id": estimates[0].strategy_id,
            "total_max_daily": round(total_max, 2),
            "total_current_daily": round(total_current, 2),
            "overall_utilization": f"{overall_pct:.1%}",
            "overall_level": level.value,
            "symbols": len(estimates),
            "by_symbol": [e.to_dict() for e in estimates],
        }
