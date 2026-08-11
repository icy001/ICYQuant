"""
Enterprise Risk Dashboard — Unified enterprise risk overview and visualization hub.

Aggregates real-time risk, VaR, stress results, exposure, PnL, and capital
into a single enterprise-wide risk dashboard.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DashboardSnapshot:
    """Snapshot of the enterprise risk dashboard."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    portfolio_value: float = 0.0
    # Real-time risk
    portfolio_risk_score: float = 0.0
    exposure_gross: float = 0.0
    exposure_net: float = 0.0
    margin_usage_pct: float = 0.0
    # PnL
    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0
    mtd_pnl: float = 0.0
    ytd_pnl: float = 0.0
    # VaR / CVaR
    var_95_1d: float = 0.0
    var_99_1d: float = 0.0
    cvar_95: float = 0.0
    cvar_99: float = 0.0
    # Stress
    worst_stress_loss_pct: float = 0.0
    worst_stress_scenario: str = ""
    stress_scenarios_failed: int = 0
    # Capital
    capital_ratio: float = 0.0
    capital_surplus: float = 0.0
    # Drawdown
    current_drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    # Alerts
    active_alerts: int = 0
    critical_alerts: int = 0
    # Status
    overall_status: str = "healthy"
    metadata: dict[str, Any] = field(default_factory=dict)


class EnterpriseRiskDashboard:
    """
    Unified enterprise risk overview and visualization hub.

    Aggregates all risk dimensions into a single dashboard:
    - Real-Time Risk (portfolio risk score, exposure, margin)
    - PnL (daily, MTD, YTD)
    - VaR / CVaR (95%, 99% confidence)
    - Stress Test Results
    - Capital Adequacy
    - Drawdown Monitoring
    - Active Alerts

    Usage::

        dashboard = EnterpriseRiskDashboard()
        await dashboard.initialize()
        await dashboard.update(analytics_results)
        snapshot = await dashboard.get_snapshot()
    """

    def __init__(self) -> None:
        self._snapshot = DashboardSnapshot()
        self._history: list[DashboardSnapshot] = []
        self._max_history = 1000
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the enterprise dashboard."""
        self._initialized = True

    async def update(self, analytics_results: dict[str, Any]) -> DashboardSnapshot:
        """
        Update dashboard with latest analytics results.

        Parameters
        ----------
        analytics_results : dict
            Full analytics pipeline results.

        Returns
        -------
        DashboardSnapshot
            Updated snapshot.
        """
        async with self._lock:
            snapshot = DashboardSnapshot()

            # Portfolio value
            var_data = analytics_results.get("var", {})
            stress_data = analytics_results.get("stress_testing", {})
            capital_data = analytics_results.get("capital_adequacy", {})
            mc_data = analytics_results.get("monte_carlo", {})

            # Extract values
            snapshot.portfolio_value = var_data.get("portfolio_value", 0)

            # PnL
            snapshot.daily_pnl = analytics_results.get("daily_pnl", 0)
            snapshot.daily_pnl_pct = analytics_results.get("daily_pnl_pct", 0)
            snapshot.mtd_pnl = analytics_results.get("mtd_pnl", 0)
            snapshot.ytd_pnl = analytics_results.get("ytd_pnl", 0)

            # VaR
            for entry in var_data.get("var_entries", []):
                if entry.get("confidence_level") == 0.95 and entry.get("time_horizon_days") == 1:
                    snapshot.var_95_1d = entry.get("var_value", 0)

            # CVaR
            for entry in analytics_results.get("cvar", {}).get("cvar_entries", []):
                if entry.get("confidence_level") == 0.95:
                    snapshot.cvar_95 = entry.get("cvar_value", 0)
                if entry.get("confidence_level") == 0.99:
                    snapshot.cvar_99 = entry.get("cvar_value", 0)

            # Stress
            snapshot.worst_stress_loss_pct = stress_data.get("worst_case_loss_pct", 0)
            snapshot.worst_stress_scenario = stress_data.get("worst_case_scenario", "")
            snapshot.stress_scenarios_failed = stress_data.get("failed", 0)

            # Capital
            ratios = capital_data.get("ratios", {})
            snapshot.capital_ratio = ratios.get("car_pct", 0)
            snapshot.capital_surplus = capital_data.get("capital_surplus", 0)

            # Drawdown
            snapshot.current_drawdown_pct = analytics_results.get("current_drawdown_pct", 0)
            snapshot.max_drawdown_pct = analytics_results.get("max_drawdown_pct", 0)

            # Alerts
            snapshot.active_alerts = analytics_results.get("active_alerts", 0)
            snapshot.critical_alerts = analytics_results.get("critical_alerts", 0)

            # Overall status
            snapshot.overall_status = self._determine_status(snapshot)

            # Store
            self._snapshot = snapshot
            self._history.append(snapshot)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

            return snapshot

    async def get_snapshot(self) -> dict[str, Any]:
        """Get current dashboard snapshot."""
        s = self._snapshot
        return {
            "timestamp": s.timestamp.isoformat(),
            "portfolio_value": s.portfolio_value,
            "real_time_risk": {
                "portfolio_risk_score": s.portfolio_risk_score,
                "exposure_gross": s.exposure_gross,
                "exposure_net": s.exposure_net,
                "margin_usage_pct": s.margin_usage_pct,
            },
            "pnl": {
                "daily_pnl": s.daily_pnl,
                "daily_pnl_pct": s.daily_pnl_pct,
                "mtd_pnl": s.mtd_pnl,
                "ytd_pnl": s.ytd_pnl,
            },
            "var_cvar": {
                "var_95_1d": s.var_95_1d,
                "var_99_1d": s.var_99_1d,
                "cvar_95": s.cvar_95,
                "cvar_99": s.cvar_99,
            },
            "stress": {
                "worst_loss_pct": s.worst_stress_loss_pct,
                "worst_scenario": s.worst_stress_scenario,
                "scenarios_failed": s.stress_scenarios_failed,
            },
            "capital": {
                "capital_ratio_pct": s.capital_ratio,
                "capital_surplus": s.capital_surplus,
            },
            "drawdown": {
                "current_pct": s.current_drawdown_pct,
                "max_pct": s.max_drawdown_pct,
            },
            "alerts": {
                "active": s.active_alerts,
                "critical": s.critical_alerts,
            },
            "overall_status": s.overall_status,
        }

    async def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get dashboard snapshot history."""
        async with self._lock:
            recent = self._history[-limit:]
        return [
            {
                "timestamp": s.timestamp.isoformat(),
                "portfolio_value": s.portfolio_value,
                "daily_pnl": s.daily_pnl,
                "var_95_1d": s.var_95_1d,
                "overall_status": s.overall_status,
            }
            for s in recent
        ]

    def _determine_status(self, snapshot: DashboardSnapshot) -> str:
        """Determine overall dashboard status."""
        if snapshot.critical_alerts > 0:
            return "critical"
        if snapshot.stress_scenarios_failed > 3:
            return "critical"
        if snapshot.capital_ratio < 8:
            return "critical"
        if snapshot.worst_stress_loss_pct > 30:
            return "warning"
        if snapshot.active_alerts > 5:
            return "warning"
        if snapshot.current_drawdown_pct > 15:
            return "warning"
        return "healthy"
