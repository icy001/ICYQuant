"""Overview Dashboard.

Top-level system overview showing:
- Overall system health
- Key metrics at a glance (PnL, NAV, AUM, orders today)
- Active alerts summary
- Service status summary

Usage::

    dashboard = OverviewDashboard(health_monitor, alert_engine, metrics_collector)
    overview = dashboard.generate()
    print(overview.to_dict())
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.monitoring.health.service_health import ServiceHealthMonitor, HealthReport
from services.monitoring.alert.rule_engine import AlertRuleEngine
from services.monitoring.metrics.collector import MetricsCollector
from services.monitoring.health.dependency_health import DependencyChecker


@dataclass
class SystemOverview:
    """Top-level system overview snapshot."""

    system_status: str = "Unknown"
    uptime_seconds: float = 0.0
    services_healthy: int = 0
    services_total: int = 0
    dependencies_available: int = 0
    dependencies_total: int = 0
    active_alerts: int = 0
    critical_alerts: int = 0
    orders_today: int = 0
    trades_today: int = 0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    nav: float = 0.0
    aum: float = 0.0
    drawdown_pct: float = 0.0
    sharpe: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system_status": self.system_status,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "uptime_str": self._format_uptime(),
            "services": f"{self.services_healthy}/{self.services_total}",
            "dependencies": f"{self.dependencies_available}/{self.dependencies_total}",
            "active_alerts": self.active_alerts,
            "critical_alerts": self.critical_alerts,
            "orders_today": self.orders_today,
            "trades_today": self.trades_today,
            "pnl": round(self.pnl, 2),
            "pnl_pct": f"{round(self.pnl_pct * 100, 2)}%" if self.pnl_pct else "0%",
            "nav": round(self.nav, 2),
            "aum": round(self.aum, 2),
            "drawdown_pct": f"{round(self.drawdown_pct, 2)}%",
            "sharpe": round(self.sharpe, 2),
            "timestamp": self.timestamp,
        }

    def _format_uptime(self) -> str:
        seconds = int(self.uptime_seconds)
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, secs = divmod(rem, 60)
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        return f"{minutes}m {secs}s"


class OverviewDashboard:
    """Generates the top-level system overview dashboard."""

    def __init__(
        self,
        health_monitor: ServiceHealthMonitor,
        dependency_checker: Optional[DependencyChecker] = None,
        alert_engine: Optional[AlertRuleEngine] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ) -> None:
        self._health = health_monitor
        self._deps = dependency_checker
        self._alerts = alert_engine
        self._metrics = metrics_collector
        self._start_time = time.time()

    def generate(self) -> SystemOverview:
        """Generate the system overview snapshot."""
        # Health
        health_report = self._health.check_all()
        services_healthy = sum(
            1 for s in health_report.services.values()
            if s.get("status") == "Healthy"
        )

        # Dependencies
        dep_report = None
        if self._deps:
            dep_report = self._deps.check_all()
            deps_available = sum(
                1 for d in dep_report.dependencies.values()
                if d.get("status") == "Available"
            )
            deps_total = len(dep_report.dependencies)
        else:
            deps_available = 0
            deps_total = 0

        # Alerts
        active_alerts = 0
        critical_alerts = 0
        if self._alerts:
            active = self._alerts.get_active_alerts()
            active_alerts = len(active)
            from services.monitoring.alert.rule_engine import AlertSeverity
            critical_alerts = len(
                [a for a in active if a.severity in (AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY)]
            )

        # Metrics
        orders_today = 0
        trades_today = 0
        pnl = 0.0
        nav = 0.0
        aum = 0.0
        drawdown = 0.0
        sharpe = 0.0
        if self._metrics:
            biz = self._metrics.get_business()
            orders_today = biz.total_orders
            trades_today = biz.total_trades
            pnl = biz.pnl
            nav = biz.nav
            aum = biz.aum
            drawdown = biz.drawdown_pct
            sharpe = biz.sharpe

        # Overall status
        if services_healthy == len(health_report.services) and active_alerts == 0:
            system_status = "Healthy"
        elif services_healthy > 0 and critical_alerts == 0:
            system_status = "Degraded"
        else:
            system_status = "Unhealthy"

        # PnL percentage (approximate from NAV change)
        pnl_pct = 0.0
        if nav > 0 and pnl != 0:
            pnl_pct = pnl / (nav - pnl) if (nav - pnl) != 0 else 0.0

        return SystemOverview(
            system_status=system_status,
            uptime_seconds=time.time() - self._start_time,
            services_healthy=services_healthy,
            services_total=len(health_report.services),
            dependencies_available=deps_available,
            dependencies_total=deps_total,
            active_alerts=active_alerts,
            critical_alerts=critical_alerts,
            orders_today=orders_today,
            trades_today=trades_today,
            pnl=pnl,
            pnl_pct=pnl_pct,
            nav=nav,
            aum=aum,
            drawdown_pct=drawdown,
            sharpe=sharpe,
        )

    def generate_dict(self) -> Dict[str, Any]:
        """Generate overview as a dict."""
        return self.generate().to_dict()
