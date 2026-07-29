"""Institutional Monitoring & Operations Center — Unified Service.

Aggregates all monitoring sub-systems into a single operations center:
- Service health monitoring
- Metrics collection & aggregation
- Alert rule engine & notification
- Auto-recovery & circuit breakers
- Dashboard generation (overview, trading, risk, portfolio, infrastructure)
- SLA tracking

Usage::

    center = MonitoringCenter()

    # Health checks
    center.health.register("OMS", check_oms_fn)
    report = center.health.check_all()

    # Metrics
    center.collector.collect_business("pnl", 250000.0)
    center.aggregator.record("order_latency", 12.5)

    # Alerts
    center.alerts.add_rule(AlertRule(...))
    triggered = center.evaluate_alerts()

    # Dashboards
    overview = center.get_overview()
    trading = center.get_trading_dashboard()
    risk = center.get_risk_dashboard()
    portfolio = center.get_portfolio_dashboard()
    infra = center.get_infrastructure_dashboard()

    # SLA
    sla = center.get_sla_report()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.monitoring.health.service_health import ServiceHealthMonitor, HealthReport
from services.monitoring.health.dependency_health import DependencyChecker
from services.monitoring.health.readiness import ReadinessProbe, ProbeType

from services.monitoring.metrics.collector import MetricsCollector, BusinessMetrics, SystemMetrics
from services.monitoring.metrics.aggregator import MetricsAggregator, AggregationWindow
from services.monitoring.metrics.timeseries import TimeSeriesStore
from services.monitoring.metrics.exporter import MetricsExporter, ExportFormat

from services.monitoring.alert.rule_engine import AlertRuleEngine, AlertRule, Alert, AlertSeverity
from services.monitoring.alert.notifier import AlertNotifier, NotificationChannel, ChannelConfig
from services.monitoring.alert.escalation import EscalationManager, EscalationPolicy

from services.monitoring.recovery.circuit_breaker import CircuitBreakerRegistry, CircuitBreaker
from services.monitoring.recovery.auto_recovery import AutoRecovery, RecoveryAction
from services.monitoring.recovery.failover import FailoverManager, FailoverTarget

from services.monitoring.dashboard.overview import OverviewDashboard, SystemOverview
from services.monitoring.dashboard.trading import TradingDashboard, TradingSnapshot
from services.monitoring.dashboard.risk import RiskDashboard, RiskSnapshot
from services.monitoring.dashboard.portfolio import PortfolioDashboard, PortfolioSnapshot
from services.monitoring.dashboard.infrastructure import InfrastructureDashboard, InfrastructureSnapshot


@dataclass
class SLAReport:
    """Service Level Agreement report."""

    service_name: str
    availability_pct: float = 100.0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    error_rate_pct: float = 0.0
    total_checks: int = 0
    failed_checks: int = 0
    period_hours: float = 0.0
    recovery_time_avg_ms: float = 0.0
    uptime_seconds: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service": self.service_name,
            "availability_pct": round(self.availability_pct, 4),
            "availability_str": f"{self.availability_pct:.4f}%",
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "error_rate_pct": round(self.error_rate_pct, 4),
            "total_checks": self.total_checks,
            "failed_checks": self.failed_checks,
            "period_hours": round(self.period_hours, 2),
            "recovery_time_avg_ms": round(self.recovery_time_avg_ms, 2),
            "uptime_seconds": round(self.uptime_seconds, 1),
            "timestamp": self.timestamp,
        }


class MonitoringCenter:
    """Unified Institutional Monitoring & Operations Center.

    This is the top-level service that aggregates all monitoring
    capabilities into a single interface for operations teams.
    """

    def __init__(self) -> None:
        # Health
        self.health = ServiceHealthMonitor()
        self.dependencies = DependencyChecker()
        self.readiness = ReadinessProbe()
        self.readiness.mark_started()

        # Metrics
        self.collector = MetricsCollector()
        self.aggregator = MetricsAggregator()
        self.timeseries = TimeSeriesStore()
        self.exporter = MetricsExporter()

        # Alerts
        self.alerts = AlertRuleEngine()
        self.notifier = AlertNotifier()
        self.escalation = EscalationManager()

        # Recovery
        self.circuit_breakers = CircuitBreakerRegistry()
        self.recovery = AutoRecovery()
        self.failover = FailoverManager()

        # Dashboards
        self._overview_dashboard = OverviewDashboard(
            health_monitor=self.health,
            dependency_checker=self.dependencies,
            alert_engine=self.alerts,
            metrics_collector=self.collector,
        )
        self._trading_dashboard = TradingDashboard(metrics_collector=self.collector)
        self._risk_dashboard = RiskDashboard(metrics_collector=self.collector)
        self._portfolio_dashboard = PortfolioDashboard(metrics_collector=self.collector)
        self._infra_dashboard = InfrastructureDashboard(
            metrics_collector=self.collector,
            circuit_breaker_registry=self.circuit_breakers,
            failover_manager=self.failover,
        )

        # SLA tracking
        self._sla_start: float = time.time()
        self._sla_checks: Dict[str, List[bool]] = {}
        self._sla_latencies: Dict[str, List[float]] = {}
        self._sla_recovery_times: Dict[str, List[float]] = {}

    # ------------------------------------------------------------------
    # Health Operations
    # ------------------------------------------------------------------

    def get_health_report(self) -> Dict[str, Any]:
        """Get full health report for all services."""
        report = self.health.check_all()
        return report.to_dict()

    def get_dependency_report(self) -> Dict[str, Any]:
        """Get dependency health report."""
        report = self.dependencies.check_all()
        return report.to_dict()

    def get_readiness_status(self) -> Dict[str, Any]:
        """Get readiness probe status."""
        return self.readiness.run(ProbeType.READINESS).to_dict()

    # ------------------------------------------------------------------
    # Metrics Operations
    # ------------------------------------------------------------------

    def record_metric(self, name: str, value: float) -> None:
        """Record a metric value."""
        self.collector.collect_business(name, value)
        self.aggregator.record(name, value)
        self.timeseries.insert(name, value)

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        return self.collector.snapshot()

    def get_metric_stats(self, name: str, window: str = "5m") -> Dict[str, Any]:
        """Get aggregate stats for a metric."""
        try:
            w = AggregationWindow(window)
        except ValueError:
            w = AggregationWindow.M5
        return self.aggregator.get_stats(name, w).to_dict()

    def get_timeseries(
        self, name: str, start: Optional[float] = None, end: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Query time series data."""
        points = self.timeseries.query(name, start, end)
        return [p.to_dict() for p in points]

    def export_metrics(self, fmt: str = "dict") -> Any:
        """Export metrics in specified format."""
        try:
            f = ExportFormat(fmt)
        except ValueError:
            f = ExportFormat.DICT
        return self.exporter.export(self.collector, self.aggregator, self.timeseries, f)

    # ------------------------------------------------------------------
    # Alert Operations
    # ------------------------------------------------------------------

    def evaluate_alerts(self) -> List[Dict[str, Any]]:
        """Evaluate all alert rules against current metrics."""
        metrics = self.collector.snapshot()
        triggered = self.alerts.evaluate(metrics)
        if triggered:
            self.notifier.send_batch(triggered)
            self.escalation.check_escalations(
                self.alerts.get_active_alerts(), self.notifier
            )
        return [a.to_dict() for a in triggered]

    def get_active_alerts(
        self, severity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get currently active alerts."""
        sev = AlertSeverity(severity) if severity else None
        return [a.to_dict() for a in self.alerts.get_active_alerts(severity=sev)]

    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary."""
        return self.alerts.get_alert_summary()

    # ------------------------------------------------------------------
    # Recovery Operations
    # ------------------------------------------------------------------

    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get circuit breaker status for all services."""
        return self.circuit_breakers.status_summary()

    def get_recovery_status(self) -> Dict[str, Any]:
        """Get auto-recovery status."""
        return self.recovery.get_status()

    def get_failover_status(self) -> Dict[str, Any]:
        """Get failover status."""
        return self.failover.get_all_status()

    def run_recovery_cycle(self) -> Dict[str, Any]:
        """Run one recovery check cycle."""
        health = self.get_health_report()
        results = self.recovery.check_and_recover(health)
        failover_events = self.failover.check_and_failover(health)
        return {
            "recovery_results": [r.to_dict() for r in results],
            "failover_events": [e.to_dict() for e in failover_events],
        }

    # ------------------------------------------------------------------
    # Dashboard Operations
    # ------------------------------------------------------------------

    def get_overview(self) -> Dict[str, Any]:
        """Get system overview dashboard."""
        return self._overview_dashboard.generate_dict()

    def get_trading_dashboard(self) -> Dict[str, Any]:
        """Get trading activity dashboard."""
        return self._trading_dashboard.generate_dict()

    def get_risk_dashboard(self) -> Dict[str, Any]:
        """Get risk monitoring dashboard."""
        return self._risk_dashboard.generate_dict()

    def get_portfolio_dashboard(self) -> Dict[str, Any]:
        """Get portfolio monitoring dashboard."""
        return self._portfolio_dashboard.generate_dict()

    def get_infrastructure_dashboard(self) -> Dict[str, Any]:
        """Get infrastructure monitoring dashboard."""
        return self._infra_dashboard.generate_dict()

    def get_all_dashboards(self) -> Dict[str, Any]:
        """Get all dashboards at once."""
        return {
            "overview": self.get_overview(),
            "trading": self.get_trading_dashboard(),
            "risk": self.get_risk_dashboard(),
            "portfolio": self.get_portfolio_dashboard(),
            "infrastructure": self.get_infrastructure_dashboard(),
            "alerts": self.get_alert_summary(),
            "circuit_breakers": self.get_circuit_breaker_status(),
            "failover": self.get_failover_status(),
        }

    # ------------------------------------------------------------------
    # SLA Operations
    # ------------------------------------------------------------------

    def record_sla_check(self, service: str, success: bool, latency_ms: float) -> None:
        """Record an SLA check for a service."""
        self._sla_checks.setdefault(service, []).append(success)
        self._sla_latencies.setdefault(service, []).append(latency_ms)

    def get_sla_report(self, service: Optional[str] = None) -> Dict[str, Any]:
        """Get SLA report for one or all services."""
        if service:
            return self._compute_sla(service).to_dict()

        reports = {}
        for svc in self._sla_checks:
            reports[svc] = self._compute_sla(svc).to_dict()
        return reports

    def _compute_sla(self, service: str) -> SLAReport:
        checks = self._sla_checks.get(service, [])
        latencies = self._sla_latencies.get(service, [])
        recoveries = self._sla_recovery_times.get(service, [])

        total = len(checks)
        failed = sum(1 for c in checks if not c)
        availability = (total - failed) / max(total, 1) * 100.0
        error_rate = failed / max(total, 1) * 100.0

        avg_lat = sum(latencies) / max(len(latencies), 1)
        sorted_lat = sorted(latencies)
        p99_lat = (
            sorted_lat[int(len(sorted_lat) * 0.99)]
            if len(sorted_lat) >= 100
            else (sorted_lat[-1] if sorted_lat else 0.0)
        )

        avg_recovery = sum(recoveries) / max(len(recoveries), 1)
        uptime = time.time() - self._sla_start

        return SLAReport(
            service_name=service,
            availability_pct=availability,
            avg_latency_ms=avg_lat,
            p99_latency_ms=p99_lat,
            error_rate_pct=error_rate,
            total_checks=total,
            failed_checks=failed,
            period_hours=uptime / 3600.0,
            recovery_time_avg_ms=avg_recovery,
            uptime_seconds=uptime,
        )


# Backward-compatible alias for the old MonitoringService
# The old MonitoringService expected a MonitoringManager, but now
# MonitoringCenter is self-contained. Provide a factory for old code.
MonitoringService = MonitoringCenter  # type: ignore[assignment]
