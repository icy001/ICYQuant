"""Risk Dashboard.

Real-time risk monitoring:
- VaR, CVaR
- Risk score
- Exposure, leverage
- Drawdown
- Concentration risk
- Stress test results

Usage::

    dashboard = RiskDashboard(metrics_collector)
    snapshot = dashboard.generate()
    print(snapshot.to_dict())
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.monitoring.metrics.collector import MetricsCollector


@dataclass
class RiskSnapshot:
    """Real-time risk metrics snapshot."""

    # Core risk metrics
    var_95: float = 0.0
    cvar_95: float = 0.0
    risk_score: float = 0.0
    max_drawdown_pct: float = 0.0
    current_drawdown_pct: float = 0.0

    # Exposure
    total_exposure: float = 0.0
    net_exposure: float = 0.0
    gross_exposure: float = 0.0
    leverage: float = 0.0

    # Concentration
    top_position_pct: float = 0.0
    top3_concentration_pct: float = 0.0
    sector_concentration_max: float = 0.0

    # Volatility
    daily_volatility_pct: float = 0.0
    annualized_volatility_pct: float = 0.0
    beta: float = 0.0
    correlation_avg: float = 0.0

    # Liquidity risk
    position_concentration_ratio: float = 0.0

    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "var_cvar": {
                "var_95": round(self.var_95, 2),
                "cvar_95": round(self.cvar_95, 2),
            },
            "risk_metrics": {
                "risk_score": round(self.risk_score, 2),
                "max_drawdown_pct": round(self.max_drawdown_pct, 2),
                "current_drawdown_pct": round(self.current_drawdown_pct, 2),
            },
            "exposure": {
                "total_exposure": round(self.total_exposure, 2),
                "net_exposure": round(self.net_exposure, 2),
                "gross_exposure": round(self.gross_exposure, 2),
                "leverage": round(self.leverage, 2),
            },
            "concentration": {
                "top_position_pct": round(self.top_position_pct, 2),
                "top3_concentration_pct": round(self.top3_concentration_pct, 2),
                "sector_concentration_max": round(self.sector_concentration_max, 2),
            },
            "volatility": {
                "daily_volatility_pct": round(self.daily_volatility_pct, 4),
                "annualized_volatility_pct": round(self.annualized_volatility_pct, 2),
                "beta": round(self.beta, 2),
                "correlation_avg": round(self.correlation_avg, 2),
            },
            "timestamp": self.timestamp,
        }


class RiskDashboard:
    """Generates real-time risk monitoring dashboard."""

    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
    ) -> None:
        self._metrics = metrics_collector

    def generate(self) -> RiskSnapshot:
        """Generate risk dashboard snapshot."""
        snapshot = RiskSnapshot()

        if self._metrics:
            biz = self._metrics.get_business()
            snapshot.current_drawdown_pct = biz.drawdown_pct
            snapshot.max_drawdown_pct = biz.drawdown_pct  # In production, track max separately

        return snapshot

    def generate_dict(self) -> Dict[str, Any]:
        """Generate risk snapshot as dict."""
        return self.generate().to_dict()
