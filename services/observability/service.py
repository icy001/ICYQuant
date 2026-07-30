from typing import Dict, List, Optional
from datetime import datetime

from .tracing import DistributedTracing, Tracer, Span, Trace
from .metrics import MetricsCollector, Counter, Gauge, Histogram, MetricsRegistry
from .logging import LogManager, CentralizedLogger, LogEntry
from .alerting import AlertEngine, Alert, AlertRule, AlertSeverity, NotificationDispatcher
from .ai_monitor import AIMonitor, AIServiceStatus, ModelHealth
from .gpu_monitor import GPUMonitor, GPUClusterStatus, GPUStats
from .inference_monitor import InferenceMonitor, InferenceMetrics
from .cost_analyzer import CostAnalyzer, CostBreakdown, MonthlyCostReport
from .slo_manager import SLOManager, SLOStatusReport, SLODefinition
from .sla_manager import SLAManager, SLAReport, SLAIncident
from .anomaly_detector import AnomalyDetector, AnomalyDetectionResult
from .rca_engine import RCAEngine, RCAResult, IncidentContext
from .dashboard import DashboardManager, DashboardSnapshot
from .collector import MetricCollector
from .metric import Metric


class ObservabilityService:
    def __init__(self, collector: Optional[MetricCollector] = None):
        self.collector = collector or MetricCollector()
        self.tracing = DistributedTracing()
        self.metrics = MetricsCollector()
        self.log_manager = LogManager()
        self.alert_engine = AlertEngine()
        self.notification_dispatcher = NotificationDispatcher()
        self.ai_monitor = AIMonitor()
        self.gpu_monitor = GPUMonitor()
        self.inference_monitor = InferenceMonitor()
        self.cost_analyzer = CostAnalyzer()
        self.slo_manager = SLOManager()
        self.sla_manager = SLAManager()
        self.anomaly_detector = AnomalyDetector()
        self.rca_engine = RCAEngine()
        self.dashboard = DashboardManager()

    def record(self, metric: Metric):
        self.collector.collect(metric)

    def get_tracer(self, service_name: str) -> Tracer:
        return self.tracing.get_tracer(service_name)

    def get_logger(self, service_name: str) -> CentralizedLogger:
        return self.log_manager.get_logger(service_name)

    def get_system_status(self) -> Dict:
        gpu_status = self.gpu_monitor.get_cluster_status()
        ai_status = self.ai_monitor.get_service_status()
        active_alerts = self.alert_engine.get_active_alerts()

        overall = "HEALTHY"
        if gpu_status.status == "CRITICAL" or ai_status.overall_status == "UNHEALTHY":
            overall = "CRITICAL"
        elif gpu_status.status == "DEGRADED" or ai_status.overall_status == "DEGRADED":
            overall = "DEGRADED"

        return {
            "system": overall,
            "gpu": self.gpu_monitor.get_cluster_status_dict(),
            "ai": {
                "status": ai_status.overall_status,
                "models": [m.__dict__ for m in ai_status.models],
            },
            "active_alerts": len(active_alerts),
            "timestamp": datetime.now().isoformat(),
        }

    def get_trace(self, trace_id: str) -> Optional[Dict]:
        traces = self.tracing.get_all_traces()
        for trace in traces:
            if trace.trace_id == trace_id:
                return {
                    "trace_id": trace.trace_id,
                    "service": trace.service,
                    "spans": [
                        {
                            "span_id": s.span_id,
                            "operation": s.operation,
                            "service": s.service,
                            "status": s.status,
                            "duration_ms": round(s.duration_ms, 2),
                            "parent_id": s.parent_id,
                            "attributes": s.attributes,
                        }
                        for s in trace.spans
                    ],
                    "has_errors": trace.has_errors,
                }
        return None

    def get_ai_status(self) -> Dict:
        ai_status = self.ai_monitor.get_service_status()
        inference = {}
        for model_name in self.ai_monitor._models:
            inference[model_name] = self.inference_monitor.get_metrics(model_name)

        return {
            "overall_status": ai_status.overall_status,
            "models": [m.__dict__ for m in ai_status.models],
            "inference": {
                k: {
                    "avg_latency_ms": v.avg_latency_ms,
                    "p95_latency_ms": v.p95_latency_ms,
                    "success_rate": v.success_rate,
                    "total_requests": v.total_requests,
                }
                for k, v in inference.items()
            },
        }

    def get_cost_report(self) -> Dict:
        summary = self.cost_analyzer.get_cost_summary()
        total = self.cost_analyzer.get_total_cost()
        today = self.cost_analyzer.get_daily_cost()

        return {
            "total_cost": total,
            "currency": self.cost_analyzer._currency,
            "by_category": summary,
            "today": {
                "total": today.total_amount,
                "entries": today.entries_count,
            },
        }

    def get_exposure_report(self) -> Dict:
        return {
            "metrics": self.metrics.get_metrics(),
            "counters": self.metrics.registry.get_counter_names(),
            "gauges": self.metrics.registry.get_gauge_names(),
            "histograms": self.metrics.registry.get_histogram_names(),
        }

    def run_stress_test(self, scenario: str) -> Dict:
        return {
            "scenario": scenario,
            "status": "simulated",
            "message": f"Stress test for {scenario} would be executed via the risk engine",
        }

    def get_alerts(self, severity: Optional[str] = None) -> List[Dict]:
        alerts = self.alert_engine.get_active_alerts(severity)
        return [
            {
                "alert_id": a.alert_id,
                "rule_id": a.rule_id,
                "rule_name": a.rule_name,
                "metric": a.metric_name,
                "current_value": a.current_value,
                "severity": a.severity,
                "status": a.status,
                "message": a.message,
                "timestamp": a.timestamp.isoformat(),
            }
            for a in alerts
        ]

    def get_anomalies(self, limit: int = 20) -> List[Dict]:
        anomalies = self.anomaly_detector.get_recent_anomalies(limit=limit)
        return [
            {
                "metric": a.metric_name,
                "is_anomaly": a.is_anomaly,
                "type": a.anomaly_type,
                "severity": a.severity,
                "value": a.current_value,
                "z_score": a.z_score,
                "timestamp": a.timestamp.isoformat(),
            }
            for a in anomalies
        ]

    def perform_rca(
        self,
        incident_id: str,
        title: str,
        description: str,
        affected_service: str,
        severity: str = "HIGH",
        symptoms: Optional[List[str]] = None,
        metrics: Optional[Dict[str, float]] = None,
    ) -> Dict:
        from .rca_engine import IncidentContext
        incident = IncidentContext(
            incident_id=incident_id,
            title=title,
            description=description,
            affected_service=affected_service,
            severity=severity,
            symptoms=symptoms or [],
        )
        result = self.rca_engine.analyze(incident, metrics=metrics)
        return {
            "incident_id": result.incident_id,
            "root_cause": result.root_cause.description if result.root_cause else "Unknown",
            "category": result.root_cause.category if result.root_cause else "UNKNOWN",
            "confidence": result.confidence,
            "recommendations": result.recommended_actions,
            "summary": result.summary,
        }

    def get_dashboard_snapshot(self) -> Dict:
        gpu_status = self.gpu_monitor.get_cluster_status()
        ai_status = self.ai_monitor.get_service_status()
        active_alerts = self.alert_engine.get_active_alerts()

        system_health = "HEALTHY"
        if gpu_status.status == "CRITICAL" or ai_status.overall_status == "UNHEALTHY":
            system_health = "CRITICAL"
        elif gpu_status.status == "DEGRADED" or ai_status.overall_status == "DEGRADED":
            system_health = "DEGRADED"

        self.dashboard.build_system_panel({
            "status": system_health,
            "timestamp": datetime.now().isoformat(),
        })
        self.dashboard.build_ai_panel({
            "status": ai_status.overall_status,
            "models": [m.__dict__ for m in ai_status.models],
        })
        self.dashboard.build_gpu_panel(self.gpu_monitor.get_cluster_status_dict())
        self.dashboard.build_alerts_panel([
            {"id": a.alert_id, "severity": a.severity, "message": a.message}
            for a in active_alerts
        ])

        snapshot = self.dashboard.create_snapshot(
            system_health=system_health,
            ai_health=ai_status.overall_status,
            trading_health="HEALTHY",
            risk_health="HEALTHY",
            active_alerts=len(active_alerts),
        )

        return {
            "snapshot_id": snapshot.snapshot_id,
            "timestamp": snapshot.timestamp.isoformat(),
            "system_health": snapshot.system_health,
            "ai_health": snapshot.ai_health,
            "trading_health": snapshot.trading_health,
            "risk_health": snapshot.risk_health,
            "active_alerts": snapshot.active_alerts,
            "panels": [
                {"id": p.panel_id, "title": p.title, "type": p.panel_type, "data": p.data}
                for p in snapshot.panels
            ],
        }

    def get_slo_status(self) -> List[Dict]:
        return [
            {
                "slo_id": s.slo_id,
                "name": s.name,
                "status": s.status,
                "current_value": s.current_value,
                "target_value": s.target_value,
                "remaining_budget": s.remaining_error_budget,
            }
            for s in self.slo_manager.get_all_statuses()
        ]

    def get_sla_status(self) -> Dict:
        report = self.sla_manager.generate_report()
        return {
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "total_incidents": report.total_incidents,
            "compliance_rate": report.compliance_rate,
            "by_sla": report.by_sla,
        }
