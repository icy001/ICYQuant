"""Tests for Dashboards (overview, trading, risk, portfolio, infrastructure)
and the unified MonitoringCenter service."""

import time

from services.monitoring.health.service_health import ServiceHealthMonitor, ServiceStatus
from services.monitoring.health.dependency_health import DependencyChecker
from services.monitoring.alert.rule_engine import AlertRuleEngine, AlertRule, AlertSeverity
from services.monitoring.alert.notifier import AlertNotifier, ChannelConfig, NotificationChannel
from services.monitoring.metrics.collector import MetricsCollector, BusinessMetrics, SystemMetrics
from services.monitoring.metrics.aggregator import MetricsAggregator
from services.monitoring.metrics.timeseries import TimeSeriesStore
from services.monitoring.metrics.exporter import MetricsExporter

from services.monitoring.dashboard.overview import OverviewDashboard, SystemOverview
from services.monitoring.dashboard.trading import TradingDashboard, TradingSnapshot
from services.monitoring.dashboard.risk import RiskDashboard, RiskSnapshot
from services.monitoring.dashboard.portfolio import PortfolioDashboard, PortfolioSnapshot
from services.monitoring.dashboard.infrastructure import InfrastructureDashboard, InfrastructureSnapshot

from services.monitoring.service import MonitoringCenter, SLAReport


# =========================================================================
# Overview Dashboard Tests
# =========================================================================


class TestOverviewDashboard:
    """Tests for OverviewDashboard."""

    def test_generate_basic_overview(self):
        health = ServiceHealthMonitor()
        health.register("OMS", lambda: (ServiceStatus.HEALTHY, 10.0, "ok"))

        dashboard = OverviewDashboard(health_monitor=health)
        overview = dashboard.generate()

        assert isinstance(overview, SystemOverview)
        assert overview.system_status == "Healthy"
        assert overview.services_healthy == 1
        assert overview.services_total == 1

    def test_overview_with_alerts(self):
        health = ServiceHealthMonitor()
        health.register("OMS", lambda: (ServiceStatus.HEALTHY, 10.0, "ok"))

        alerts = AlertRuleEngine()
        alerts.add_rule(AlertRule(
            name="critical_test",
            description="test",
            severity=AlertSeverity.CRITICAL,
            condition_fn=lambda m: True,
            cooldown_seconds=0,
        ))
        alerts.evaluate({})

        dashboard = OverviewDashboard(
            health_monitor=health,
            alert_engine=alerts,
        )
        overview = dashboard.generate()
        assert overview.active_alerts == 1
        assert overview.critical_alerts == 1

    def test_overview_with_metrics(self):
        health = ServiceHealthMonitor()
        health.register("OMS", lambda: (ServiceStatus.HEALTHY, 10.0, "ok"))

        collector = MetricsCollector()
        collector.collect_business("pnl", 50000.0)
        collector.collect_business("nav", 1000000.0)
        collector.collect_business("aum", 50000000.0)
        collector.collect_business("drawdown_pct", 5.0)
        collector.collect_business("sharpe", 1.5)

        dashboard = OverviewDashboard(
            health_monitor=health,
            metrics_collector=collector,
        )
        overview = dashboard.generate()
        assert overview.pnl == 50000.0
        assert overview.nav == 1000000.0
        assert overview.aum == 50000000.0
        assert overview.drawdown_pct == 5.0
        assert overview.sharpe == 1.5

    def test_overview_degraded_status(self):
        health = ServiceHealthMonitor()
        health.register("OMS", lambda: (ServiceStatus.HEALTHY, 10.0, "ok"))
        health.register("Risk", lambda: (ServiceStatus.DEGRADED, 150.0, "slow"))

        dashboard = OverviewDashboard(health_monitor=health)
        overview = dashboard.generate()
        assert overview.system_status == "Degraded"

    def test_overview_unhealthy_with_critical_alerts(self):
        health = ServiceHealthMonitor()
        health.register("OMS", lambda: (ServiceStatus.UNHEALTHY, 0.0, "down"))

        alerts = AlertRuleEngine()
        alerts.add_rule(AlertRule(
            name="crit",
            description="crit",
            severity=AlertSeverity.CRITICAL,
            condition_fn=lambda m: True,
            cooldown_seconds=0,
        ))
        alerts.evaluate({})

        dashboard = OverviewDashboard(health_monitor=health, alert_engine=alerts)
        overview = dashboard.generate()
        assert overview.system_status == "Unhealthy"

    def test_overview_to_dict(self):
        health = ServiceHealthMonitor()
        health.register("OMS", lambda: (ServiceStatus.HEALTHY, 10.0, "ok"))

        dashboard = OverviewDashboard(health_monitor=health)
        d = dashboard.generate_dict()
        assert d["system_status"] == "Healthy"
        assert "uptime_str" in d
        assert "pnl" in d


# =========================================================================
# Trading Dashboard Tests
# =========================================================================


class TestTradingDashboard:
    """Tests for TradingDashboard."""

    def test_generate_empty(self):
        dashboard = TradingDashboard()
        snapshot = dashboard.generate()
        assert isinstance(snapshot, TradingSnapshot)
        assert snapshot.total_orders == 0

    def test_generate_with_metrics(self):
        collector = MetricsCollector()
        collector.collect_business("total_orders", 1500)
        collector.collect_business("total_trades", 1200)
        collector.collect_business("orders_per_sec", 2.5)
        collector.collect_business("trades_per_sec", 2.0)
        collector.collect_business("fill_rate_pct", 95.5)

        dashboard = TradingDashboard(metrics_collector=collector)
        snapshot = dashboard.generate()
        assert snapshot.total_orders == 1500
        assert snapshot.total_trades == 1200
        assert snapshot.orders_per_sec == 2.5
        assert snapshot.trades_per_sec == 2.0
        assert snapshot.fill_rate_pct == 95.5

    def test_to_dict(self):
        collector = MetricsCollector()
        collector.collect_business("total_orders", 100)

        dashboard = TradingDashboard(metrics_collector=collector)
        d = dashboard.generate_dict()
        assert d["orders"]["total"] == 100
        assert "trades" in d
        assert "quality" in d


# =========================================================================
# Risk Dashboard Tests
# =========================================================================


class TestRiskDashboard:
    """Tests for RiskDashboard."""

    def test_generate_empty(self):
        dashboard = RiskDashboard()
        snapshot = dashboard.generate()
        assert isinstance(snapshot, RiskSnapshot)

    def test_generate_with_metrics(self):
        collector = MetricsCollector()
        collector.collect_business("drawdown_pct", 8.5)

        dashboard = RiskDashboard(metrics_collector=collector)
        snapshot = dashboard.generate()
        assert snapshot.current_drawdown_pct == 8.5

    def test_to_dict(self):
        dashboard = RiskDashboard()
        d = dashboard.generate_dict()
        assert "var_cvar" in d
        assert "risk_metrics" in d
        assert "exposure" in d


# =========================================================================
# Portfolio Dashboard Tests
# =========================================================================


class TestPortfolioDashboard:
    """Tests for PortfolioDashboard."""

    def test_generate_empty(self):
        dashboard = PortfolioDashboard()
        snapshot = dashboard.generate()
        assert isinstance(snapshot, PortfolioSnapshot)

    def test_generate_with_metrics(self):
        collector = MetricsCollector()
        collector.collect_business("nav", 10000000.0)
        collector.collect_business("aum", 50000000.0)
        collector.collect_business("pnl", 250000.0)
        collector.collect_business("sharpe", 2.1)
        collector.collect_business("win_rate", 0.65)
        collector.collect_business("profit_factor", 1.8)

        dashboard = PortfolioDashboard(metrics_collector=collector)
        snapshot = dashboard.generate()
        assert snapshot.nav == 10000000.0
        assert snapshot.aum == 50000000.0
        assert snapshot.daily_pnl == 250000.0
        assert snapshot.sharpe == 2.1
        assert snapshot.win_rate == 0.65
        assert snapshot.profit_factor == 1.8

    def test_to_dict(self):
        collector = MetricsCollector()
        collector.collect_business("nav", 10000000.0)

        dashboard = PortfolioDashboard(metrics_collector=collector)
        d = dashboard.generate_dict()
        assert d["core"]["nav"] == 10000000.0
        assert "allocation" in d
        assert "positions" in d
        assert "pnl" in d


# =========================================================================
# Infrastructure Dashboard Tests
# =========================================================================


class TestInfrastructureDashboard:
    """Tests for InfrastructureDashboard."""

    def test_generate_empty(self):
        dashboard = InfrastructureDashboard()
        snapshot = dashboard.generate()
        assert isinstance(snapshot, InfrastructureSnapshot)

    def test_generate_with_metrics(self):
        collector = MetricsCollector()
        collector.collect_system("cpu_pct", 45.0)
        collector.collect_system("memory_pct", 60.0)
        collector.collect_system("disk_pct", 30.0)
        collector.collect_system("redis_available", True)
        collector.collect_system("redis_latency_ms", 2.5)
        collector.collect_system("kafka_available", True)
        collector.collect_system("postgres_available", True)
        collector.collect_system("api_latency_p50", 25.0)
        collector.collect_system("api_latency_p99", 100.0)
        collector.collect_system("api_error_rate", 0.001)

        dashboard = InfrastructureDashboard(metrics_collector=collector)
        snapshot = dashboard.generate()
        assert snapshot.cpu_pct == 45.0
        assert snapshot.memory_pct == 60.0
        assert snapshot.redis_status == "Available"
        assert snapshot.kafka_status == "Available"
        assert snapshot.api_latency_p50 == 25.0
        assert snapshot.api_error_rate == 0.001

    def test_unavailable_dependencies(self):
        collector = MetricsCollector()
        collector.collect_system("redis_available", False)
        collector.collect_system("kafka_available", False)
        collector.collect_system("postgres_available", False)

        dashboard = InfrastructureDashboard(metrics_collector=collector)
        snapshot = dashboard.generate()
        assert snapshot.redis_status == "Unavailable"
        assert snapshot.kafka_status == "Unavailable"
        assert snapshot.postgres_status == "Unavailable"

    def test_to_dict(self):
        dashboard = InfrastructureDashboard()
        d = dashboard.generate_dict()
        assert "resources" in d
        assert "dependencies" in d
        assert "api" in d
        assert "circuit_breakers" in d


# =========================================================================
# MonitoringCenter Integration Tests
# =========================================================================


class TestMonitoringCenter:
    """Tests for the unified MonitoringCenter."""

    def test_create_center(self):
        center = MonitoringCenter()
        assert center.health is not None
        assert center.collector is not None
        assert center.alerts is not None
        assert center.circuit_breakers is not None
        assert center.recovery is not None
        assert center.failover is not None

    def test_get_overview(self):
        center = MonitoringCenter()
        center.health.register("OMS", lambda: (ServiceStatus.HEALTHY, 10.0, "ok"))
        overview = center.get_overview()
        assert overview["system_status"] == "Healthy"

    def test_get_health_report(self):
        center = MonitoringCenter()
        center.health.register("OMS", lambda: (ServiceStatus.HEALTHY, 10.0, "ok"))
        report = center.get_health_report()
        assert report["overall_status"] == "Healthy"
        assert "OMS" in report["services"]

    def test_record_and_get_metrics(self):
        center = MonitoringCenter()
        center.record_metric("test_metric", 42.0)
        snapshot = center.get_metrics_snapshot()
        assert snapshot["custom_gauges"]["test_metric"] == 42.0

    def test_get_metric_stats(self):
        center = MonitoringCenter()
        center.record_metric("latency", 10.0)
        center.record_metric("latency", 20.0)
        center.record_metric("latency", 30.0)
        stats = center.get_metric_stats("latency", "5m")
        assert stats["count"] == 3
        assert stats["avg"] == 20.0

    def test_evaluate_alerts(self):
        center = MonitoringCenter()
        center.alerts.add_rule(AlertRule(
            name="test_alert",
            description="Always fires",
            severity=AlertSeverity.WARNING,
            condition_fn=lambda m: True,
            cooldown_seconds=0,
        ))
        triggered = center.evaluate_alerts()
        assert len(triggered) == 1

    def test_get_all_dashboards(self):
        center = MonitoringCenter()
        center.health.register("OMS", lambda: (ServiceStatus.HEALTHY, 10.0, "ok"))
        dashboards = center.get_all_dashboards()
        assert "overview" in dashboards
        assert "trading" in dashboards
        assert "risk" in dashboards
        assert "portfolio" in dashboards
        assert "infrastructure" in dashboards
        assert "alerts" in dashboards
        assert "circuit_breakers" in dashboards
        assert "failover" in dashboards

    def test_sla_tracking(self):
        center = MonitoringCenter()
        center.record_sla_check("OMS", True, 10.0)
        center.record_sla_check("OMS", True, 12.0)
        center.record_sla_check("OMS", False, 0.0)

        report = center.get_sla_report("OMS")
        assert report["service"] == "OMS"
        # 2/3 = 66.67% availability
        assert 60.0 <= report["availability_pct"] <= 70.0

    def test_sla_all_services(self):
        center = MonitoringCenter()
        center.record_sla_check("OMS", True, 10.0)
        center.record_sla_check("Risk", True, 5.0)

        reports = center.get_sla_report()
        assert "OMS" in reports
        assert "Risk" in reports

    def test_circuit_breaker_status(self):
        center = MonitoringCenter()
        status = center.get_circuit_breaker_status()
        assert "total" in status

    def test_recovery_status(self):
        center = MonitoringCenter()
        status = center.get_recovery_status()
        assert "actions_count" in status
        assert "total_recoveries" in status

    def test_failover_status(self):
        center = MonitoringCenter()
        status = center.get_failover_status()
        assert isinstance(status, dict)

    def test_run_recovery_cycle(self):
        center = MonitoringCenter()
        result = center.run_recovery_cycle()
        assert "recovery_results" in result
        assert "failover_events" in result

    def test_export_metrics_dict(self):
        center = MonitoringCenter()
        center.record_metric("test", 100.0)
        exported = center.export_metrics("dict")
        assert "business" in exported
        assert "system" in exported

    def test_export_metrics_prometheus(self):
        center = MonitoringCenter()
        exported = center.export_metrics("prometheus")
        assert isinstance(exported, str)
        assert "icyquant_" in exported


# =========================================================================
# Metrics Sub-module Tests
# =========================================================================


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_collect_business_metrics(self):
        collector = MetricsCollector()
        collector.collect_business("pnl", 50000.0)
        collector.collect_business("nav", 1000000.0)
        biz = collector.get_business()
        assert biz.pnl == 50000.0
        assert biz.nav == 1000000.0

    def test_collect_system_metrics(self):
        collector = MetricsCollector()
        collector.collect_system("cpu_pct", 45.0)
        collector.collect_system("redis_available", False)
        sys = collector.get_system()
        assert sys.cpu_pct == 45.0
        assert sys.redis_available is False

    def test_counter_operations(self):
        collector = MetricsCollector()
        assert collector.increment_counter("errors") == 1
        assert collector.increment_counter("errors", 5) == 6
        assert collector.get_counter("errors") == 6
        collector.reset_counter("errors")
        assert collector.get_counter("errors") == 0

    def test_snapshot(self):
        collector = MetricsCollector()
        collector.collect_business("pnl", 100.0)
        collector.increment_counter("orders", 10)
        snapshot = collector.snapshot()
        assert snapshot["business"]["pnl"] == 100.0
        assert snapshot["counters"]["orders"] == 10

    def test_reset(self):
        collector = MetricsCollector()
        collector.collect_business("pnl", 100.0)
        collector.reset()
        assert collector.get_business().pnl == 0.0

    def test_business_metrics_to_dict(self):
        bm = BusinessMetrics(pnl=50000.0, nav=1000000.0, sharpe=1.5)
        d = bm.to_dict()
        assert d["pnl"] == 50000.0
        assert d["sharpe"] == 1.5

    def test_system_metrics_to_dict(self):
        sm = SystemMetrics(cpu_pct=45.0, redis_available=True)
        d = sm.to_dict()
        assert d["cpu_pct"] == 45.0
        assert d["redis_available"] is True


class TestMetricsAggregator:
    """Tests for MetricsAggregator."""

    def test_record_and_get_stats(self):
        agg = MetricsAggregator()
        agg.record("latency", 10.0)
        agg.record("latency", 20.0)
        agg.record("latency", 30.0)

        from services.monitoring.metrics.aggregator import AggregationWindow
        stats = agg.get_stats("latency", AggregationWindow.M5)
        assert stats.count == 3
        assert stats.min == 10.0
        assert stats.max == 30.0
        assert stats.avg == 20.0
        assert stats.p50 == 20.0

    def test_percentiles(self):
        agg = MetricsAggregator()
        for v in range(1, 101):
            agg.record("test", float(v))

        from services.monitoring.metrics.aggregator import AggregationWindow
        stats = agg.get_stats("test", AggregationWindow.ALL)
        assert stats.count == 100
        assert 49 <= stats.p50 <= 51
        assert 94 <= stats.p95 <= 96
        assert 98 <= stats.p99 <= 100

    def test_list_metrics(self):
        agg = MetricsAggregator()
        agg.record("a", 1.0)
        agg.record("b", 2.0)
        assert set(agg.list_metrics()) == {"a", "b"}

    def test_empty_metric_returns_default(self):
        agg = MetricsAggregator()
        from services.monitoring.metrics.aggregator import AggregationWindow
        stats = agg.get_stats("nonexistent", AggregationWindow.M5)
        assert stats.count == 0
        assert stats.avg == 0.0

    def test_clear(self):
        agg = MetricsAggregator()
        agg.record("test", 1.0)
        agg.clear()
        assert len(agg.list_metrics()) == 0


class TestTimeSeriesStore:
    """Tests for TimeSeriesStore."""

    def test_insert_and_query(self):
        store = TimeSeriesStore()
        store.insert("cpu", 45.0, timestamp=100.0)
        store.insert("cpu", 47.0, timestamp=200.0)
        store.insert("cpu", 42.0, timestamp=300.0)

        points = store.query("cpu")
        assert len(points) == 3
        assert points[0].value == 45.0
        assert points[-1].value == 42.0

    def test_range_query(self):
        store = TimeSeriesStore()
        for i in range(10):
            store.insert("test", float(i), timestamp=float(i * 10))

        points = store.query("test", start=30.0, end=70.0)
        assert len(points) == 5  # timestamps 30,40,50,60,70

    def test_latest(self):
        store = TimeSeriesStore()
        store.insert("test", 1.0, timestamp=100.0)
        store.insert("test", 2.0, timestamp=200.0)
        assert store.latest("test") == 2.0

    def test_latest_nonexistent(self):
        store = TimeSeriesStore()
        assert store.latest("nonexistent") is None

    def test_query_values(self):
        store = TimeSeriesStore()
        store.insert("test", 1.0, timestamp=100.0)
        store.insert("test", 2.0, timestamp=200.0)
        values = store.query_values("test")
        assert values == [1.0, 2.0]

    def test_downsample(self):
        store = TimeSeriesStore()
        # 10 points every 10 seconds
        for i in range(10):
            store.insert("test", float(i * 10), timestamp=float(i * 10))

        result = store.downsample("test", interval_seconds=20.0)
        # 10 points (0,10,...,90) at 20s interval → 5 buckets (0,1,2,3,4)
        assert len(result) == 5

    def test_cleanup(self):
        store = TimeSeriesStore(retention_seconds=1.0)
        store.insert("test", 1.0, timestamp=time.time() - 100.0)
        store.insert("test", 2.0, timestamp=time.time())
        removed = store.cleanup()
        assert removed == 1

    def test_point_count_and_series_count(self):
        store = TimeSeriesStore()
        store.insert("a", 1.0)
        store.insert("a", 2.0)
        store.insert("b", 3.0)
        assert store.point_count == 3
        assert store.series_count == 2

    def test_create_series_with_metadata(self):
        store = TimeSeriesStore()
        ts = store.create_series("api_latency", unit="ms", description="API latency in ms")
        assert ts.name == "api_latency"
        assert ts.unit == "ms"
        assert ts.description == "API latency in ms"


class TestMetricsExporter:
    """Tests for MetricsExporter."""

    def test_export_dict(self):
        collector = MetricsCollector()
        collector.collect_business("pnl", 50000.0)

        exporter = MetricsExporter()
        result = exporter.export(collector, fmt="dict")
        assert result["business"]["pnl"] == 50000.0

    def test_export_json(self):
        collector = MetricsCollector()
        exporter = MetricsExporter()
        result = exporter.export(collector, fmt="json")
        assert isinstance(result, str)
        assert "pnl" in result

    def test_export_prometheus(self):
        collector = MetricsCollector()
        collector.collect_business("pnl", 50000.0)
        collector.collect_system("cpu_pct", 45.0)

        exporter = MetricsExporter()
        result = exporter.export(collector, fmt="prometheus")
        assert "icyquant_pnl 50000.0" in result
        assert "icyquant_cpu_pct 45.0" in result
        assert "# HELP" in result
        assert "# TYPE" in result


# =========================================================================
# SLAReport Tests
# =========================================================================


class TestSLAReport:
    """Tests for SLAReport."""

    def test_create_and_to_dict(self):
        report = SLAReport(
            service_name="OMS",
            availability_pct=99.95,
            avg_latency_ms=15.0,
            p99_latency_ms=50.0,
            error_rate_pct=0.05,
            total_checks=10000,
            failed_checks=5,
            period_hours=24.0,
            recovery_time_avg_ms=200.0,
        )
        d = report.to_dict()
        assert d["service"] == "OMS"
        assert d["availability_pct"] == 99.95
        assert "99.95" in d["availability_str"]
        assert d["avg_latency_ms"] == 15.0
        assert d["p99_latency_ms"] == 50.0
        assert d["error_rate_pct"] == 0.05
