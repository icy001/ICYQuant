from services.observability import (
    RCAEngine,
    IncidentContext,
    RCAResult,
    RCACategory,
    RootCause,
)


class TestRCAEngine:
    def test_analyze_timeout_incident(self):
        engine = RCAEngine()
        incident = IncidentContext(
            incident_id="inc1",
            title="Order Timeout",
            description="Orders timing out during peak hours",
            affected_service="execution",
            severity="HIGH",
            symptoms=["timeout", "high latency"],
        )
        metrics = {
            "queue_depth": 500,
            "db_latency_ms": 20,
        }
        result = engine.analyze(incident, metrics=metrics)
        assert result.root_cause is not None
        assert result.root_cause.category == RCACategory.RESOURCE.value
        assert "queue" in result.root_cause.description.lower()
        assert len(result.recommended_actions) > 0

    def test_analyze_db_latency_incident(self):
        engine = RCAEngine()
        incident = IncidentContext(
            incident_id="inc2",
            title="Slow Queries",
            description="Database queries taking too long",
            affected_service="database",
            severity="HIGH",
            symptoms=["timeout", "latency"],
        )
        metrics = {
            "queue_depth": 5,
            "db_latency_ms": 800,
        }
        result = engine.analyze(incident, metrics=metrics)
        assert result.root_cause is not None
        assert result.root_cause.category == RCACategory.DATABASE.value

    def test_analyze_memory_incident(self):
        engine = RCAEngine()
        incident = IncidentContext(
            incident_id="inc3",
            title="OOM Error",
            description="Service ran out of memory",
            affected_service="ai_service",
            severity="CRITICAL",
            symptoms=["memory", "oom"],
        )
        metrics = {
            "memory_used_pct": 95,
        }
        result = engine.analyze(incident, metrics=metrics)
        assert result.root_cause is not None
        assert result.root_cause.category == RCACategory.RESOURCE.value

    def test_analyze_error_rate_incident(self):
        engine = RCAEngine()
        incident = IncidentContext(
            incident_id="inc4",
            title="High Error Rate",
            description="Many requests failing",
            affected_service="api_gateway",
            severity="HIGH",
            symptoms=["error rate", "failure"],
        )
        metrics = {
            "error_rate": 0.6,
        }
        result = engine.analyze(incident, metrics=metrics)
        assert result.root_cause is not None
        assert result.root_cause.category == RCACategory.CODE_DEFECT.value

    def test_analyze_network_incident(self):
        engine = RCAEngine()
        incident = IncidentContext(
            incident_id="inc5",
            title="Connection Lost",
            description="Cannot connect to downstream service",
            affected_service="api_gateway",
            severity="HIGH",
            symptoms=["connectivity", "connection"],
        )
        result = engine.analyze(incident)
        assert result.root_cause is not None
        assert result.root_cause.category == RCACategory.NETWORK.value

    def test_analyze_unknown_symptom(self):
        engine = RCAEngine()
        incident = IncidentContext(
            incident_id="inc6",
            title="Unknown Issue",
            description="Something went wrong",
            affected_service="unknown",
            severity="LOW",
            symptoms=["unknown issue"],
        )
        result = engine.analyze(incident)
        assert result.root_cause is not None

    def test_analysis_history(self):
        engine = RCAEngine()
        for i in range(3):
            incident = IncidentContext(
                incident_id=f"inc_{i}",
                title=f"Incident {i}",
                description=f"Description {i}",
                affected_service="test",
                severity="LOW",
                symptoms=["timeout"],
            )
            engine.analyze(incident, metrics={"queue_depth": 100})
        history = engine.get_analysis_history()
        assert len(history) == 3

    def test_recommendations(self):
        engine = RCAEngine()
        incident = IncidentContext(
            incident_id="inc7",
            title="Network Issue",
            description="Network connectivity problems",
            affected_service="test",
            severity="HIGH",
            symptoms=["connectivity"],
        )
        result = engine.analyze(incident)
        assert len(result.recommended_actions) > 0


class TestAnomalyDetector:
    def test_detect_normal(self):
        from services.observability import AnomalyDetector
        detector = AnomalyDetector(sensitivity=2.0)
        for v in [10, 11, 9, 10.5, 10.2, 9.8, 10.1]:
            detector.add_data_point("test_metric", v)
        result = detector.detect("test_metric", 10.0)
        assert result.is_anomaly is False

    def test_detect_spike(self):
        from services.observability import AnomalyDetector
        detector = AnomalyDetector(sensitivity=2.0)
        for v in [10, 11, 9, 10.5, 10.2, 9.8, 10.1]:
            detector.add_data_point("test_metric", v)
        result = detector.detect("test_metric", 50.0)
        assert result.is_anomaly is True
        assert result.anomaly_type == "SPIKE"

    def test_detect_drop(self):
        from services.observability import AnomalyDetector
        detector = AnomalyDetector(sensitivity=2.0)
        for v in [100, 101, 99, 100.5, 100.2, 99.8, 100.1]:
            detector.add_data_point("test_metric", v)
        result = detector.detect("test_metric", 10.0)
        assert result.is_anomaly is True
        assert result.anomaly_type == "DROP"

    def test_insufficient_data(self):
        from services.observability import AnomalyDetector
        detector = AnomalyDetector()
        detector.add_data_point("test", 10)
        result = detector.detect("test", 20)
        assert result.is_anomaly is False
        assert result.anomaly_type == "INSUFFICIENT_DATA"
