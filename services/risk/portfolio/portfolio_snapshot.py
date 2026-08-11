"""
Portfolio Snapshot — Immutable point-in-time snapshot of portfolio state.

Captures positions, balances, risk metrics, and market data for
use across the portfolio and intraday risk pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class PositionSnapshot:
    """Single position at a point in time."""

    symbol: str
    quantity: float
    avg_cost: float
    market_price: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    side: str = "LONG"
    instrument_type: str = "EQUITY"
    sector: str = ""
    asset_class: str = ""
    currency: str = "USD"
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def pnl_pct(self) -> float:
        """PnL as percentage of cost basis."""
        cost_basis = abs(self.quantity) * self.avg_cost
        if cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / cost_basis) * 100


@dataclass(frozen=True)
class PortfolioSnapshot:
    """Complete portfolio state at a single point in time."""

    snapshot_id: str
    account_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ---- Positions ----
    positions: dict[str, PositionSnapshot] = field(default_factory=dict)

    # ---- Balances ----
    total_equity: float = 0.0
    cash_balance: float = 0.0
    margin_used: float = 0.0
    margin_available: float = 0.0
    buying_power: float = 0.0

    # ---- Aggregated PnL ----
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    monthly_pnl: float = 0.0

    # ---- Risk Metrics ----
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    leverage_ratio: float = 0.0
    margin_ratio: float = 0.0
    portfolio_risk_score: float = 0.0

    # ---- Drawdown ----
    peak_equity: float = 0.0
    current_drawdown_pct: float = 0.0
    max_historical_drawdown_pct: float = 0.0

    # ---- Concentration ----
    top_holding_pct: float = 0.0
    sector_concentration: dict[str, float] = field(default_factory=dict)

    # ---- Greeks (for options) ----
    portfolio_delta: float = 0.0
    portfolio_gamma: float = 0.0
    portfolio_theta: float = 0.0
    portfolio_vega: float = 0.0
    portfolio_rho: float = 0.0

    # ---- Factor Exposures ----
    factor_exposures: dict[str, float] = field(default_factory=dict)

    # ---- Correlation ----
    correlation_matrix: dict[str, dict[str, float]] = field(default_factory=dict)
    cluster_labels: dict[str, str] = field(default_factory=dict)

    # ---- Liquidity ----
    portfolio_liquidity_score: float = 100.0
    avg_exit_time_hours: float = 0.0

    # ---- Metadata ----
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def position_count(self) -> int:
        return len(self.positions)

    @property
    def is_net_long(self) -> bool:
        return self.net_exposure > 0

    @property
    def is_net_short(self) -> bool:
        return self.net_exposure < 0

    @property
    def is_flat(self) -> bool:
        return abs(self.net_exposure) < 1e-6

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "account_id": self.account_id,
            "timestamp": self.timestamp.isoformat(),
            "position_count": self.position_count,
            "total_equity": self.total_equity,
            "cash_balance": self.cash_balance,
            "margin_used": self.margin_used,
            "margin_available": self.margin_available,
            "buying_power": self.buying_power,
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "total_realized_pnl": self.total_realized_pnl,
            "daily_pnl": self.daily_pnl,
            "weekly_pnl": self.weekly_pnl,
            "monthly_pnl": self.monthly_pnl,
            "gross_exposure": self.gross_exposure,
            "net_exposure": self.net_exposure,
            "long_exposure": self.long_exposure,
            "short_exposure": self.short_exposure,
            "leverage_ratio": self.leverage_ratio,
            "margin_ratio": self.margin_ratio,
            "portfolio_risk_score": self.portfolio_risk_score,
            "peak_equity": self.peak_equity,
            "current_drawdown_pct": self.current_drawdown_pct,
            "max_historical_drawdown_pct": self.max_historical_drawdown_pct,
            "top_holding_pct": self.top_holding_pct,
            "sector_concentration": dict(self.sector_concentration),
            "portfolio_delta": self.portfolio_delta,
            "portfolio_gamma": self.portfolio_gamma,
            "portfolio_theta": self.portfolio_theta,
            "portfolio_vega": self.portfolio_vega,
            "portfolio_rho": self.portfolio_rho,
            "factor_exposures": dict(self.factor_exposures),
            "portfolio_liquidity_score": self.portfolio_liquidity_score,
            "avg_exit_time_hours": self.avg_exit_time_hours,
        }
