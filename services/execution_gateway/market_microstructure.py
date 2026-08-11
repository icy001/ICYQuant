"""Market Microstructure — Market microstructure analysis for execution.

Analyzes fine-grained market dynamics including order book structure,
trade flow, and hidden liquidity patterns. Provides microstructure
data for execution algorithms and routing decisions.

Analysis Domains:
    - Bid/Ask Spread dynamics
    - Order Book Imbalance
    - Trade Velocity & Arrival
    - Queue Position estimation
    - Hidden Liquidity detection

Usage::

    analyzer = MarketMicrostructureAnalyzer()
    micro = await analyzer.analyze(symbol, order_book_snapshot)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MicrostructureSnapshot:
    """Market microstructure analysis snapshot.

    Attributes:
        symbol: Trading symbol
        timestamp: Analysis timestamp (epoch seconds)
        spread_bps: Current bid-ask spread in bps
        mid_price: Mid-point price
        bid_depth: Total visible bid quantity
        ask_depth: Total visible ask quantity
        imbalance: Order book imbalance (-1 to 1)
        trade_velocity: Recent trade rate (trades/sec)
        queue_position_estimate: Estimated queue position percentile
        hidden_liquidity_prob: Probability of hidden liquidity
        effective_spread_bps: Effective spread (trade-based)
        realized_spread_bps: Realized spread
        price_impact_bps: Price impact of recent trades
        volatility_bps: Short-term realized volatility
    """

    symbol: str = ""
    timestamp: float = 0.0
    spread_bps: float = 0.0
    mid_price: float = 0.0
    bid_depth: float = 0.0
    ask_depth: float = 0.0
    imbalance: float = 0.0
    trade_velocity: float = 0.0
    queue_position_estimate: float = 0.5
    hidden_liquidity_prob: float = 0.0
    effective_spread_bps: float = 0.0
    realized_spread_bps: float = 0.0
    price_impact_bps: float = 0.0
    volatility_bps: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_liquid(self) -> bool:
        """Whether market is considered liquid."""
        return self.spread_bps < 5.0 and self.bid_depth > 0 and self.ask_depth > 0

    @property
    def buy_pressure(self) -> float:
        """Buying pressure indicator (0-1)."""
        return max(0.0, min(1.0, (self.imbalance + 1.0) / 2.0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "spread_bps": self.spread_bps,
            "mid_price": self.mid_price,
            "bid_depth": self.bid_depth,
            "ask_depth": self.ask_depth,
            "imbalance": self.imbalance,
            "trade_velocity": self.trade_velocity,
            "queue_position_estimate": self.queue_position_estimate,
            "hidden_liquidity_prob": self.hidden_liquidity_prob,
            "effective_spread_bps": self.effective_spread_bps,
            "realized_spread_bps": self.realized_spread_bps,
            "price_impact_bps": self.price_impact_bps,
            "volatility_bps": self.volatility_bps,
            "is_liquid": self.is_liquid,
            "buy_pressure": self.buy_pressure,
        }


class MarketMicrostructureAnalyzer:
    """Market microstructure analysis engine.

    Analyzes order book dynamics and trade flow to provide
    microstructure signals for execution algorithms.

    Attributes:
        _snapshots: Recent microstructure snapshots
        _max_history: Maximum snapshots to retain
    """

    def __init__(self) -> None:
        self._snapshots: dict[str, list[MicrostructureSnapshot]] = {}
        self._max_history = 100

    # ── Analysis ───────────────────────────────────────────────────

    async def analyze(
        self,
        symbol: str,
        order_book: Optional[dict[str, Any]] = None,
        trade_data: Optional[dict[str, Any]] = None,
    ) -> MicrostructureSnapshot:
        """Analyze market microstructure for a symbol.

        Args:
            symbol: Trading symbol
            order_book: Order book snapshot data
            trade_data: Recent trade data

        Returns:
            MicrostructureSnapshot
        """
        import time

        # Extract from provided data or use defaults
        bids = (order_book or {}).get("bids", [])
        asks = (order_book or {}).get("asks", [])

        # Compute spread
        best_bid = bids[0][0] if bids else 0.0
        best_ask = asks[0][0] if asks else 0.0
        mid_price = (best_bid + best_ask) / 2.0 if best_bid and best_ask else 0.0
        spread_bps = (
            (best_ask - best_bid) / mid_price * 10000
            if mid_price > 0 and best_ask > best_bid
            else 0.0
        )

        # Compute depths
        bid_depth = sum(qty for _, qty in bids[:5]) if bids else 0.0
        ask_depth = sum(qty for _, qty in asks[:5]) if asks else 0.0

        # Order book imbalance
        total_depth = bid_depth + ask_depth
        imbalance = (
            (bid_depth - ask_depth) / total_depth if total_depth > 0 else 0.0
        )

        # Trade velocity from trade data
        trade_velocity = (trade_data or {}).get("trades_per_second", 0.0)

        # Hidden liquidity detection
        hidden_prob = self._detect_hidden_liquidity(bids, asks, order_book or {})

        # Effective spread estimation
        effective_spread = self._estimate_effective_spread(
            spread_bps, trade_data or {}
        )

        snapshot = MicrostructureSnapshot(
            symbol=symbol,
            timestamp=time.time(),
            spread_bps=spread_bps,
            mid_price=mid_price,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            imbalance=imbalance,
            trade_velocity=trade_velocity,
            queue_position_estimate=0.5,
            hidden_liquidity_prob=hidden_prob,
            effective_spread_bps=effective_spread,
            realized_spread_bps=effective_spread * 0.7,
            price_impact_bps=spread_bps * 0.3,
            volatility_bps=(trade_data or {}).get("volatility_bps", spread_bps * 0.5),
            metadata={
                "best_bid": best_bid,
                "best_ask": best_ask,
                "bid_levels": len(bids),
                "ask_levels": len(asks),
            },
        )

        self._record_snapshot(symbol, snapshot)
        return snapshot

    # ── Advanced Analysis ──────────────────────────────────────────

    async def analyze_order_book_imbalance(
        self,
        symbol: str,
        depth_levels: int = 5,
    ) -> dict[str, Any]:
        """Analyze order book imbalance across depth levels.

        Args:
            symbol: Trading symbol
            depth_levels: Number of levels to analyze

        Returns:
            Imbalance analysis dictionary
        """
        snapshots = self._snapshots.get(symbol, [])
        if not snapshots:
            return {"imbalance": 0.0, "trend": "neutral"}

        latest = snapshots[-1]
        trend = "buy" if latest.imbalance > 0.05 else ("sell" if latest.imbalance < -0.05 else "neutral")

        return {
            "imbalance": latest.imbalance,
            "trend": trend,
            "depth_levels": depth_levels,
            "bid_depth": latest.bid_depth,
            "ask_depth": latest.ask_depth,
        }

    async def detect_hidden_liquidity(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Detect hidden liquidity patterns.

        Args:
            symbol: Trading symbol

        Returns:
            Hidden liquidity analysis
        """
        snapshots = self._snapshots.get(symbol, [])
        if not snapshots:
            return {"probability": 0.0, "detected": False}

        latest = snapshots[-1]
        return {
            "probability": latest.hidden_liquidity_prob,
            "detected": latest.hidden_liquidity_prob > 0.3,
        }

    async def analyze_queue_position(
        self,
        symbol: str,
        price: float,
        side: str,
    ) -> dict[str, Any]:
        """Estimate queue position for a limit order.

        Args:
            symbol: Trading symbol
            price: Limit price
            side: BUY or SELL

        Returns:
            Queue position analysis
        """
        snapshots = self._snapshots.get(symbol, [])
        if not snapshots:
            return {"position_pct": 50.0, "estimated_fill_time_seconds": 0.0}

        latest = snapshots[-1]
        # Simple estimation: depth-based position
        total_depth = latest.bid_depth if side.upper() == "BUY" else latest.ask_depth
        position_pct = 50.0  # Default middle

        # Estimate fill time based on trade velocity
        fill_time = (
            total_depth / max(latest.trade_velocity, 0.001)
            if latest.trade_velocity > 0
            else 0.0
        )

        return {
            "position_pct": position_pct,
            "estimated_fill_time_seconds": fill_time,
            "trade_velocity": latest.trade_velocity,
        }

    # ── Internal Methods ───────────────────────────────────────────

    def _detect_hidden_liquidity(
        self,
        bids: list,
        asks: list,
        order_book: dict[str, Any],
    ) -> float:
        """Detect probability of hidden (iceberg) orders.

        Returns:
            Probability 0-1
        """
        # Heuristic: large trades at same price level suggest hidden liquidity
        if "large_trades" in order_book:
            return min(order_book["large_trades"] * 0.1, 1.0)
        return 0.1  # Low default probability

    def _estimate_effective_spread(
        self,
        quoted_spread_bps: float,
        trade_data: dict[str, Any],
    ) -> float:
        """Estimate effective spread from trade data.

        Args:
            quoted_spread_bps: Quoted spread
            trade_data: Trade data

        Returns:
            Estimated effective spread in bps
        """
        # Effective spread is typically lower than quoted spread
        effective_multiplier = trade_data.get("effective_spread_ratio", 0.7)
        return quoted_spread_bps * effective_multiplier

    def _record_snapshot(
        self,
        symbol: str,
        snapshot: MicrostructureSnapshot,
    ) -> None:
        """Record a microstructure snapshot."""
        if symbol not in self._snapshots:
            self._snapshots[symbol] = []
        self._snapshots[symbol].append(snapshot)
        if len(self._snapshots[symbol]) > self._max_history:
            self._snapshots[symbol] = self._snapshots[symbol][-self._max_history:]

    def get_latest(self, symbol: str) -> Optional[MicrostructureSnapshot]:
        """Get latest microstructure snapshot.

        Args:
            symbol: Trading symbol

        Returns:
            Latest snapshot or None
        """
        snapshots = self._snapshots.get(symbol, [])
        return snapshots[-1] if snapshots else None

    def to_dict(self) -> dict[str, Any]:
        """Serialize analyzer state."""
        return {
            "symbols_analyzed": len(self._snapshots),
            "symbols": list(self._snapshots.keys()),
        }
