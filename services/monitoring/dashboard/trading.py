"""Trading Dashboard.

Real-time trading activity monitoring:
- Orders (total, active, filled, cancelled)
- Trades (count, volume, value)
- Fill rate, average latency
- Order book depth, spread

Usage::

    dashboard = TradingDashboard(metrics_collector)
    snapshot = dashboard.generate()
    print(snapshot.to_dict())
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.monitoring.metrics.collector import MetricsCollector


@dataclass
class TradingSnapshot:
    """Real-time trading activity snapshot."""

    # Order stats
    total_orders: int = 0
    active_orders: int = 0
    filled_orders: int = 0
    cancelled_orders: int = 0
    rejected_orders: int = 0
    orders_per_sec: float = 0.0

    # Trade stats
    total_trades: int = 0
    trade_volume: float = 0.0
    trade_value: float = 0.0
    trades_per_sec: float = 0.0

    # Quality metrics
    fill_rate_pct: float = 0.0
    avg_latency_ms: float = 0.0
    avg_slippage_bps: float = 0.0
    rejection_rate_pct: float = 0.0

    # Market impact
    avg_spread_bps: float = 0.0
    market_impact_bps: float = 0.0

    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "orders": {
                "total": self.total_orders,
                "active": self.active_orders,
                "filled": self.filled_orders,
                "cancelled": self.cancelled_orders,
                "rejected": self.rejected_orders,
                "per_sec": round(self.orders_per_sec, 2),
            },
            "trades": {
                "total": self.total_trades,
                "volume": round(self.trade_volume, 4),
                "value": round(self.trade_value, 2),
                "per_sec": round(self.trades_per_sec, 2),
            },
            "quality": {
                "fill_rate_pct": round(self.fill_rate_pct, 2),
                "avg_latency_ms": round(self.avg_latency_ms, 2),
                "avg_slippage_bps": round(self.avg_slippage_bps, 2),
                "rejection_rate_pct": round(self.rejection_rate_pct, 2),
            },
            "market": {
                "avg_spread_bps": round(self.avg_spread_bps, 2),
                "market_impact_bps": round(self.market_impact_bps, 2),
            },
            "timestamp": self.timestamp,
        }


class TradingDashboard:
    """Generates real-time trading activity dashboard."""

    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
    ) -> None:
        self._metrics = metrics_collector

    def generate(self) -> TradingSnapshot:
        """Generate trading dashboard snapshot."""
        snapshot = TradingSnapshot()

        if self._metrics:
            biz = self._metrics.get_business()
            snapshot.total_orders = biz.total_orders
            snapshot.total_trades = biz.total_trades
            snapshot.orders_per_sec = biz.orders_per_sec
            snapshot.trades_per_sec = biz.trades_per_sec
            snapshot.fill_rate_pct = biz.fill_rate_pct

        return snapshot

    def generate_dict(self) -> Dict[str, Any]:
        """Generate trading snapshot as dict."""
        return self.generate().to_dict()
