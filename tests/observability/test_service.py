from services.observability import (
    SLOManager,
    SLOStatus,
    SLOType,
    SLOStatusReport,
    SLAManager,
    SLAReport,
    SLAIncident,
    SLAPriority,
    ObservabilityService,
    AnomalyDetector,
    DashboardManager,
)


class TestSLOManager:
    def test_define_slo(self):
        mgr = SLOManager()
        slo = mgr.define_slo(
            "slo1",
            "Trading Availability",
            "oms",
            SLOType.AVAILABILITY.value,
            0.9999,
        )
        assert slo.slo_id == "slo1"
        assert slo.target_value == 0.9999

    def test_record_event_on_track(self):
        mgr = SLOManager()
        mgr.define_slo("slo1", "Test", "svc", "AVAILABILITY", 0.99)
        for _ in range(100):
            mgr.record_event("slo1", is_good=True)
        status = mgr.get_status("slo1")
        assert status.status == SLOStatus.ON_TRACK.value

    def test_record_event_breached(self):
        mgr = SLOManager()
        mgr.define_slo("slo1", "Test", "svc", "AVAILABILITY", 0.99)
        for i in range(100):
            mgr.record_event("slo1", is_good=i >= 50)
        status = mgr.get_status("slo1")
        assert status.status == SLOStatus.BREACHED.value

    def test_latency_event(self):
        mgr = SLOManager()
        mgr.define_slo("slo1", "Latency", "svc", "LATENCY", 0.99)
        for _ in range(100):
            mgr.record_latency_event("slo1", 10, 50)
        status = mgr.get_status("slo1")
        assert status.current_value >= 0.9

    def test_get_all_statuses(self):
        mgr = SLOManager()
        mgr.define_slo("slo1", "SLO1", "svc", "AVAILABILITY", 0.99)
        mgr.define_slo("slo2", "SLO2", "svc", "LATENCY", 0.95)
        statuses = mgr.get_all_statuses()
        assert len(statuses) == 2

    def test_list_slos(self):
        mgr = SLOManager()
        mgr.define_slo("slo1", "SLO1", "svc", "AVAILABILITY", 0.99)
        slos = mgr.list_slos()
        assert len(slos) == 1


class TestSLAManager:
    def test_define_sla(self):
        mgr = SLAManager()
        sla = mgr.define_sla(
            "sla1",
            "P1 Response",
            "ops",
            "RESPONSE_TIME",
            0.5,
            "hours",
            SLAPriority.P1.value,
        )
        assert sla.sla_id == "sla1"

    def test_report_incident(self):
        mgr = SLAManager()
        mgr.define_sla("sla1", "SLA", "svc", "RESPONSE_TIME", 2.0, "hours")
        incident = mgr.report_incident(
            "sla1",
            "Server Down",
            "Production server not responding",
            SLAPriority.P1.value,
        )
        assert incident.incident_id is not None
        assert incident.status == "OPEN"

    def test_resolve_incident_within_sla(self):
        mgr = SLAManager()
        mgr.define_sla("sla1", "SLA", "svc", "RESPONSE_TIME", 24.0, "hours")
        incident = mgr.report_incident("sla1", "Issue", "Description")
        resolved = mgr.resolve_incident(incident.incident_id)
        assert resolved.status == "RESOLVED"
        assert resolved.met_sla is True

    def test_resolve_incident_breach(self):
        from datetime import datetime, timedelta
        mgr = SLAManager()
        mgr.define_sla("sla1", "SLA", "svc", "RESPONSE_TIME", 0.000001, "hours")
        incident = mgr.report_incident("sla1", "Issue", "Description")
        future_time = datetime.now() + timedelta(seconds=10)
        resolved = mgr.resolve_incident(incident.incident_id, resolved_at=future_time)
        assert resolved.met_sla is False

    def test_sla_status(self):
        mgr = SLAManager()
        mgr.define_sla("sla1", "SLA", "svc", "RESPONSE_TIME", 24.0, "hours")
        status = mgr.get_sla_status("sla1")
        assert "compliance_rate" in status

    def test_generate_report(self):
        mgr = SLAManager()
        mgr.define_sla("sla1", "SLA", "svc", "RESPONSE_TIME", 24.0, "hours")
        report = mgr.generate_report()
        assert report.total_incidents == 0
        assert report.compliance_rate == 1.0

    def test_list_incidents(self):
        mgr = SLAManager()
        mgr.define_sla("sla1", "SLA", "svc", "RESPONSE_TIME", 24.0, "hours")
        mgr.report_incident("sla1", "Issue1", "Desc1")
        mgr.report_incident("sla1", "Issue2", "Desc2")
        incidents = mgr.list_incidents()
        assert len(incidents) == 2


class TestObservabilityService:
    def test_create_service(self):
        svc = ObservabilityService()
        assert svc.tracing is not None
        assert svc.metrics is not None
        assert svc.ai_monitor is not None

    def test_get_system_status(self):
        svc = ObservabilityService()
        status = svc.get_system_status()
        assert "system" in status
        assert "gpu" in status
        assert "ai" in status

    def test_get_ai_status(self):
        svc = ObservabilityService()
        svc.ai_monitor.register_model("gpt-4", "LLM")
        svc.ai_monitor.update_health("gpt-4", 50, 0.01, 100)
        status = svc.get_ai_status()
        assert "overall_status" in status
        assert "models" in status

    def test_get_cost_report(self):
        svc = ObservabilityService()
        svc.cost_analyzer.record_cost("GPU", "GPU_0", 2, 25)
        report = svc.get_cost_report()
        assert "total_cost" in report

    def test_get_alerts(self):
        svc = ObservabilityService()
        alerts = svc.get_alerts()
        assert isinstance(alerts, list)

    def test_get_anomalies(self):
        svc = ObservabilityService()
        anomalies = svc.get_anomalies()
        assert isinstance(anomalies, list)

    def test_dashboard_snapshot(self):
        svc = ObservabilityService()
        snapshot = svc.get_dashboard_snapshot()
        assert "snapshot_id" in snapshot
        assert "system_health" in snapshot


class TestAnomalyDetector:
    def test_latency_anomaly(self):
        detector = AnomalyDetector(sensitivity=2.0)
        for v in [50, 55, 48, 52, 53, 51, 49]:
            detector.add_data_point("latency.api", v)
        result = detector.detect_latency_anomaly("api", 500)
        assert result.is_anomaly is True

    def test_memory_anomaly(self):
        detector = AnomalyDetector(sensitivity=2.0)
        for v in [50, 55, 48, 52, 53, 51, 49]:
            detector.add_data_point("memory.api", v)
        result = detector.detect_memory_anomaly("api", 95)
        assert result.is_anomaly is True

    def test_volume_anomaly(self):
        detector = AnomalyDetector(sensitivity=2.0)
        for v in [100, 110, 95, 105, 102, 98, 108]:
            detector.add_data_point("volume.api", v)
        result = detector.detect_volume_anomaly("api", 1000)
        assert result.is_anomaly is True


class TestDashboardManager:
    def test_create_snapshot(self):
        mgr = DashboardManager()
        mgr.build_system_panel({"status": "HEALTHY"})
        mgr.build_ai_panel({"status": "HEALTHY"})
        snapshot = mgr.create_snapshot(
            system_health="HEALTHY",
            ai_health="HEALTHY",
            trading_health="HEALTHY",
            risk_health="HEALTHY",
        )
        assert snapshot.snapshot_id is not None
        assert len(snapshot.panels) == 2

    def test_get_latest_snapshot(self):
        mgr = DashboardManager()
        snapshot = mgr.create_snapshot(system_health="HEALTHY")
        latest = mgr.get_latest_snapshot()
        assert latest is not None
        assert latest.snapshot_id == snapshot.snapshot_id
