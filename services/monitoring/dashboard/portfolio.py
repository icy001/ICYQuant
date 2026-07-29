"""Portfolio Dashboard.

Real-time portfolio monitoring:
- NAV, returns, drawdown
- Position summary
- Cash ratio
- Sector allocation
- PnL breakdown

Usage::

    dashboard = PortfolioDashboard(metrics_collector)
    snapshot = dashboard.generate()
    print(snapshot.to_dict())
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.monitoring.metrics.collector import MetricsCollector


@dataclass
class PortfolioSnapshot:
    """Real-time portfolio snapshot."""

    # Core metrics
    nav: float = 0.0
    aum: float = 0.0
    daily_return_pct: float = 0.0
    mtd_return_pct: float = 0.0
    ytd_return_pct: float = 0.0
    sharpe: float = 0.0
    drawdown_pct: float = 0.0

    # Allocation
    cash_pct: float = 0.0
    equity_pct: float = 0.0
    fixed_income_pct: float = 0.0
    other_pct: float = 0.0

    # Position summary
    total_positions: int = 0
    long_positions: int = 0
    short_positions: int = 0
    avg_position_size: float = 0.0

    # PnL
    daily_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    # Performance
    win_rate: float = 0.0
    profit_factor: float = 0.0

    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "core": {
                "nav": round(self.nav, 2),
                "aum": round(self.aum, 2),
                "daily_return_pct": round(self.daily_return_pct, 4),
                "mtd_return_pct": round(self.mtd_return_pct, 4),
                "ytd_return_pct": round(self.ytd_return_pct, 4),
                "sharpe": round(self.sharpe, 2),
                "drawdown_pct": round(self.drawdown_pct, 2),
            },
            "allocation": {
                "cash_pct": round(self.cash_pct, 2),
                "equity_pct": round(self.equity_pct, 2),
                "fixed_income_pct": round(self.fixed_income_pct, 2),
                "other_pct": round(self.other_pct, 2),
            },
            "positions": {
                "total": self.total_positions,
                "long": self.long_positions,
                "short": self.short_positions,
                "avg_size": round(self.avg_position_size, 2),
            },
            "pnl": {
                "daily_pnl": round(self.daily_pnl, 2),
                "unrealized_pnl": round(self.unrealized_pnl, 2),
                "realized_pnl": round(self.realized_pnl, 2),
            },
            "performance": {
                "win_rate": round(self.win_rate, 2),
                "profit_factor": round(self.profit_factor, 2),
            },
            "timestamp": self.timestamp,
        }


class PortfolioDashboard:
    """Generates real-time portfolio monitoring dashboard."""

    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
    ) -> None:
        self._metrics = metrics_collector

    def generate(self) -> PortfolioSnapshot:
        """Generate portfolio dashboard snapshot."""
        snapshot = PortfolioSnapshot()

        if self._metrics:
            biz = self._metrics.get_business()
            snapshot.nav = biz.nav
            snapshot.aum = biz.aum
            snapshot.sharpe = biz.sharpe
            snapshot.drawdown_pct = biz.drawdown_pct
            snapshot.daily_pnl = biz.pnl
            snapshot.win_rate = biz.win_rate
            snapshot.profit_factor = biz.profit_factor

        return snapshot

    def generate_dict(self) -> Dict[str, Any]:
        """Generate portfolio snapshot as dict."""
        return self.generate().to_dict()
