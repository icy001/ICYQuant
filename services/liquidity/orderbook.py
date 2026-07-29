"""Order Book Engine.

Maintains real-time limit order book snapshots with L1 (top of book)
and L2 (price-level aggregated) depth data.

Supports:
- Bid/Ask level maintenance and sorting
- Spread calculation (absolute and bps)
- Book depth aggregation at arbitrary levels
- Order book construction from market data
- Book comparison (before/after events)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .models import DepthLevel, OrderBook, PriceLevel, Side


# =============================================================================
# Order Book Manager
# =============================================================================


class OrderBookManager:
    """Manages and maintains order book snapshots.

    Builds order books from market data, maintains bid/ask sorting,
    and provides analysis methods for depth and spread.

    Usage:
        manager = OrderBookManager()
        book = manager.build_book(
            symbol="NVDA",
            bids=[(150.0, 5000), (149.98, 8000)],
            asks=[(150.02, 3000), (150.04, 6000)],
            last_price=150.0,
        )
        depth = manager.analyze_depth(book)
    """

    def __init__(self) -> None:
        self._books: Dict[str, OrderBook] = {}

    # -------------------------------------------------------------------------
    # Book Construction
    # -------------------------------------------------------------------------

    def build_book(
        self,
        symbol: str,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
        last_price: float = 0.0,
        daily_volume: float = 0.0,
        adv: float = 0.0,
        order_counts: Optional[Dict[str, List[int]]] = None,
    ) -> OrderBook:
        """Build an order book from price/volume tuples.

        Args:
            symbol: Trading symbol
            bids: List of (price, volume) tuples for bids
            asks: List of (price, volume) tuples for asks
            last_price: Last traded price
            daily_volume: Current day volume
            adv: Average daily volume
            order_counts: Optional dict with 'bids' and 'asks' keys containing
                         order count per level per side

        Returns:
            Constructed OrderBook
        """
        bid_levels = self._build_levels(bids, order_counts.get("bids") if order_counts else None)
        ask_levels = self._build_levels(asks, order_counts.get("asks") if order_counts else None)

        book = OrderBook(
            symbol=symbol.upper(),
            bids=bid_levels,
            asks=ask_levels,
            last_price=last_price,
            daily_volume=daily_volume,
            adv=adv,
        )
        self._books[symbol.upper()] = book
        return book

    def build_book_l1(
        self,
        symbol: str,
        bid_price: float,
        bid_volume: float,
        ask_price: float,
        ask_volume: float,
        last_price: float = 0.0,
        daily_volume: float = 0.0,
        adv: float = 0.0,
    ) -> OrderBook:
        """Build an order book from L1 (top-of-book) data only.

        Args:
            symbol: Trading symbol
            bid_price: Best bid price
            bid_volume: Best bid volume
            ask_price: Best ask price
            ask_volume: Best ask volume
            last_price: Last traded price
            daily_volume: Current day volume
            adv: Average daily volume

        Returns:
            OrderBook with single-level depth
        """
        return self.build_book(
            symbol=symbol,
            bids=[(bid_price, bid_volume)],
            asks=[(ask_price, ask_volume)],
            last_price=last_price,
            daily_volume=daily_volume,
            adv=adv,
        )

    def _build_levels(
        self,
        levels: List[Tuple[float, float]],
        order_counts: Optional[List[int]] = None,
    ) -> List[PriceLevel]:
        """Create PriceLevel objects from tuples.

        Args:
            levels: (price, volume) tuples
            order_counts: Optional order count per level

        Returns:
            Sorted list of PriceLevel objects
        """
        result = []
        for i, (price, volume) in enumerate(levels):
            count = order_counts[i] if order_counts else 0
            result.append(PriceLevel(price=price, volume=volume, order_count=count))
        return result

    # -------------------------------------------------------------------------
    # Book Retrieval
    # -------------------------------------------------------------------------

    def get_book(self, symbol: str) -> Optional[OrderBook]:
        """Get the current order book for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            OrderBook if found, None otherwise
        """
        return self._books.get(symbol.upper())

    def list_symbols(self) -> List[str]:
        """List all symbols with active order books.

        Returns:
            List of symbol strings
        """
        return list(self._books.keys())

    def update_book(self, symbol: str, book: OrderBook) -> None:
        """Update the order book for a symbol.

        Args:
            symbol: Trading symbol
            book: Updated OrderBook
        """
        self._books[symbol.upper()] = book

    # -------------------------------------------------------------------------
    # Depth Analysis
    # -------------------------------------------------------------------------

    def analyze_depth(
        self,
        book: OrderBook,
        order_quantity: float = 0.0,
        max_bps_move: float = 10.0,
    ) -> Dict[str, Any]:
        """Analyze order book depth and execution capacity.

        Computes how much volume is available before the price
        moves by a given amount in basis points.

        Args:
            book: OrderBook to analyze
            order_quantity: Reference order size (for depth_multiple)
            max_bps_move: Maximum acceptable price move in bps

        Returns:
            Depth analysis dictionary
        """
        mid = book.mid_price
        if mid <= 0:
            return self._empty_depth_response()

        # Volumes available at various price impact thresholds
        thresholds_bps = [5, 10, 25, 50]
        volumes = {}
        for t in thresholds_bps:
            target_move = mid * (t / 10000.0)
            buy_vol = self._volume_to_price_move(book.asks, mid, target_move)
            sell_vol = self._volume_to_price_move(book.bids, mid, target_move)
            volumes[f"buy_at_{t}bps"] = buy_vol
            volumes[f"sell_at_{t}bps"] = sell_vol

        # Depth multiple: how many multiples of order_quantity at best
        best_bid_vol = book.best_bid.volume if book.best_bid else 0.0
        best_ask_vol = book.best_ask.volume if book.best_ask else 0.0
        best_vol = max(best_bid_vol, best_ask_vol)

        depth_multiple = best_vol / order_quantity if order_quantity > 0 else 0.0

        level = DepthLevel.THIN
        if depth_multiple >= 50:
            level = DepthLevel.DEEP
        elif depth_multiple >= 10:
            level = DepthLevel.MODERATE
        elif depth_multiple >= 2:
            level = DepthLevel.SHALLOW

        return {
            "symbol": book.symbol,
            "level": level.value,
            "depth_multiple": round(depth_multiple, 2),
            "volume_at_5bps_buy": round(volumes["buy_at_5bps"], 2),
            "volume_at_5bps_sell": round(volumes["sell_at_5bps"], 2),
            "volume_at_10bps_buy": round(volumes["buy_at_10bps"], 2),
            "volume_at_10bps_sell": round(volumes["sell_at_10bps"], 2),
            "volume_at_25bps_buy": round(volumes["buy_at_25bps"], 2),
            "volume_at_25bps_sell": round(volumes["sell_at_25bps"], 2),
            "volume_at_50bps_buy": round(volumes["buy_at_50bps"], 2),
            "volume_at_50bps_sell": round(volumes["sell_at_50bps"], 2),
            "total_bid_volume": round(book.total_bid_volume, 2),
            "total_ask_volume": round(book.total_ask_volume, 2),
        }

    def _volume_to_price_move(
        self,
        levels: List[PriceLevel],
        start_price: float,
        max_move: float,
    ) -> float:
        """Calculate cumulative volume before a price move threshold.

        For asks: counts up to start_price + max_move
        For bids: works reversed (starting from best)

        Args:
            levels: Sorted price levels (asks ascending, bids descending)
            start_price: Reference price
            max_move: Maximum price move allowed

        Returns:
            Cumulative volume available within the price move
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

    # -------------------------------------------------------------------------
    # Book Comparison
    # -------------------------------------------------------------------------

    def compare_books(
        self,
        before: OrderBook,
        after: OrderBook,
    ) -> Dict[str, Any]:
        """Compare two order book snapshots to detect changes.

        Args:
            before: Earlier order book snapshot
            after: Later order book snapshot

        Returns:
            Comparison dictionary with delta metrics
        """
        return {
            "symbol": before.symbol,
            "spread_bps_before": round(before.spread_bps, 2),
            "spread_bps_after": round(after.spread_bps, 2),
            "spread_delta_bps": round(after.spread_bps - before.spread_bps, 2),
            "bid_volume_before": round(before.total_bid_volume, 2),
            "bid_volume_after": round(after.total_bid_volume, 2),
            "bid_volume_delta": round(after.total_bid_volume - before.total_bid_volume, 2),
            "ask_volume_before": round(before.total_ask_volume, 2),
            "ask_volume_after": round(after.total_ask_volume, 2),
            "ask_volume_delta": round(after.total_ask_volume - before.total_ask_volume, 2),
            "imbalance_before": round(before.imbalance_ratio, 4),
            "imbalance_after": round(after.imbalance_ratio, 4),
            "imbalance_delta": round(after.imbalance_ratio - before.imbalance_ratio, 4),
        }

    @staticmethod
    def _empty_depth_response() -> Dict[str, Any]:
        return {
            "symbol": "",
            "level": DepthLevel.THIN.value,
            "depth_multiple": 0.0,
            "volume_at_5bps_buy": 0.0,
            "volume_at_5bps_sell": 0.0,
            "volume_at_10bps_buy": 0.0,
            "volume_at_10bps_sell": 0.0,
            "volume_at_25bps_buy": 0.0,
            "volume_at_25bps_sell": 0.0,
            "volume_at_50bps_buy": 0.0,
            "volume_at_50bps_sell": 0.0,
            "total_bid_volume": 0.0,
            "total_ask_volume": 0.0,
        }
