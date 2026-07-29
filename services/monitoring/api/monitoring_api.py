"""Monitoring & Operations Center REST API.

FastAPI router providing endpoints for:
- System overview dashboard
- Service health checks
- Dependency health status
- Metrics collection and query
- Alert management
- Circuit breaker status
- Auto-recovery operations
- SLA reports

Endpoints:
    GET    /api/v1/monitoring/overview        System overview dashboard
    GET    /api/v1/monitoring/health           Service health report
    GET    /api/v1/monitoring/health/deps       Dependency health
    GET    /api/v1/monitoring/health/readiness  Readiness probe
    GET    /api/v1/monitoring/metrics           Metrics snapshot
    GET    /api/v1/monitoring/metrics/{name}    Metric stats & timeseries
    GET    /api/v1/monitoring/metrics/export    Export metrics (prometheus)
    GET    /api/v1/monitoring/alerts            Active alerts
    GET    /api/v1/monitoring/alerts/summary    Alert summary
    GET    /api/v1/monitoring/alerts/history    Alert history
    POST   /api/v1/monitoring/alerts/evaluate   Evaluate all rules
    GET    /api/v1/monitoring/dashboard/trading     Trading dashboard
    GET    /api/v1/monitoring/dashboard/risk        Risk dashboard
    GET    /api/v1/monitoring/dashboard/portfolio   Portfolio dashboard
    GET    /api/v1/monitoring/dashboard/infra       Infrastructure dashboard
    GET    /api/v1/monitoring/circuit-breakers      Circuit breaker status
    GET    /api/v1/monitoring/recovery              Recovery status
    POST   /api/v1/monitoring/recovery/run          Run recovery cycle
    GET    /api/v1/monitoring/sla                   SLA reports
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from services.monitoring.service import MonitoringCenter

router = APIRouter(prefix="/api/v1/monitoring", tags=["Monitoring Center"])

# Singleton instance — shared across all requests
_center = MonitoringCenter()


# =========================================================================
# System Overview
# =========================================================================

@router.get("/overview", summary="System overview dashboard")
async def get_overview():
    """Get top-level system overview with key metrics and health status."""
    return _center.get_overview()


# =========================================================================
# Health
# =========================================================================

@router.get("/health", summary="Service health report")
async def get_health():
    """Get health status for all registered services."""
    return _center.get_health_report()


@router.get("/health/deps", summary="Dependency health")
async def get_dependency_health():
    """Get health status for infrastructure dependencies."""
    return _center.get_dependency_report()


@router.get("/health/readiness", summary="Readiness probe")
async def get_readiness():
    """Kubernetes-style readiness probe."""
    result = _center.get_readiness_status()
    if not result["ready"]:
        raise HTTPException(status_code=503, detail="Service not ready")
    return result


# =========================================================================
# Metrics
# =========================================================================

@router.get("/metrics", summary="Current metrics snapshot")
async def get_metrics():
    """Get current business and system metrics snapshot."""
    return _center.get_metrics_snapshot()


@router.get("/metrics/{name}", summary="Metric stats")
async def get_metric_stats(
    name: str,
    window: str = Query("5m", description="Aggregation window: 1m, 5m, 15m, 1h, 4h, 1d"),
):
    """Get aggregate statistics for a specific metric."""
    return _center.get_metric_stats(name, window)


@router.get("/metrics/{name}/timeseries", summary="Metric timeseries")
async def get_metric_timeseries(
    name: str,
    start: Optional[float] = Query(None, description="Start timestamp (unix)"),
    end: Optional[float] = Query(None, description="End timestamp (unix)"),
):
    """Query time series data for a metric."""
    return _center.get_timeseries(name, start, end)


@router.get("/metrics/export", summary="Export metrics")
async def export_metrics(
    fmt: str = Query("dict", description="Export format: dict, json, prometheus"),
):
    """Export metrics in specified format (Prometheus, JSON, dict)."""
    if fmt == "prometheus":
        from fastapi.responses import PlainTextResponse
        text = _center.export_metrics(fmt)
        return PlainTextResponse(content=text, media_type="text/plain")
    return _center.export_metrics(fmt)


# =========================================================================
# Alerts
# =========================================================================

@router.get("/alerts", summary="Active alerts")
async def get_active_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity: info, warning, critical, emergency"),
):
    """Get currently active (firing) alerts."""
    return _center.get_active_alerts(severity)


@router.get("/alerts/summary", summary="Alert summary")
async def get_alert_summary():
    """Get alert summary with counts by severity and category."""
    return _center.get_alert_summary()


@router.get("/alerts/history", summary="Alert history")
async def get_alert_history():
    """Get alert history (last 100 alerts)."""
    history = _center.alerts.get_alert_history(limit=100)
    return [a.to_dict() for a in history]


@router.post("/alerts/evaluate", summary="Evaluate alert rules")
async def evaluate_alerts():
    """Evaluate all alert rules against current metrics and trigger notifications."""
    triggered = _center.evaluate_alerts()
    return {"triggered_count": len(triggered), "alerts": triggered}


# =========================================================================
# Dashboards
# =========================================================================

@router.get("/dashboard/trading", summary="Trading dashboard")
async def get_trading_dashboard():
    """Get real-time trading activity dashboard."""
    return _center.get_trading_dashboard()


@router.get("/dashboard/risk", summary="Risk dashboard")
async def get_risk_dashboard():
    """Get real-time risk monitoring dashboard."""
    return _center.get_risk_dashboard()


@router.get("/dashboard/portfolio", summary="Portfolio dashboard")
async def get_portfolio_dashboard():
    """Get real-time portfolio monitoring dashboard."""
    return _center.get_portfolio_dashboard()


@router.get("/dashboard/infra", summary="Infrastructure dashboard")
async def get_infrastructure_dashboard():
    """Get infrastructure monitoring dashboard."""
    return _center.get_infrastructure_dashboard()


@router.get("/dashboard/all", summary="All dashboards")
async def get_all_dashboards():
    """Get all dashboards in a single response."""
    return _center.get_all_dashboards()


# =========================================================================
# Circuit Breakers
# =========================================================================

@router.get("/circuit-breakers", summary="Circuit breaker status")
async def get_circuit_breakers():
    """Get status of all circuit breakers."""
    return _center.get_circuit_breaker_status()


# =========================================================================
# Recovery
# =========================================================================

@router.get("/recovery", summary="Recovery status")
async def get_recovery_status():
    """Get auto-recovery and failover status."""
    return {
        "recovery": _center.get_recovery_status(),
        "failover": _center.get_failover_status(),
    }


@router.post("/recovery/run", summary="Run recovery cycle")
async def run_recovery():
    """Execute one recovery cycle (health check + auto-recovery + failover)."""
    return _center.run_recovery_cycle()


# =========================================================================
# SLA
# =========================================================================

@router.get("/sla", summary="SLA reports")
async def get_sla_reports(
    service: Optional[str] = Query(None, description="Filter by service name"),
):
    """Get SLA reports for all or specific services."""
    return _center.get_sla_report(service)
