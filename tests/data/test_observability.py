from services.data.observability import (
    HealthCalculator,
    DataDashboard,
    MetricView,
    PipelineView,
    AlertCenter,
    ObservabilityService,
)


def test_health_score():
    calc = HealthCalculator()

    score = calc.calculate(0.9, 1.0)

    assert score == 0.95


def test_health_score_zero():
    calc = HealthCalculator()

    score = calc.calculate(0, 0)

    assert score == 0


def test_dashboard_render():
    dashboard = DataDashboard()

    result = dashboard.render({"rows": 100})

    assert result["status"] == "healthy"
    assert result["metrics"]["rows"] == 100


def test_metric_view():
    view = MetricView(name="null_rate", value=0.01)

    assert view.name == "null_rate"
    assert view.value == 0.01


def test_pipeline_view():
    view = PipelineView()

    result = view.status("ingestion")

    assert result["pipeline"] == "ingestion"
    assert result["status"] == "RUNNING"


def test_alert_center():
    center = AlertCenter()

    alert = {"level": "WARNING", "message": "test"}
    center.push(alert)

    assert len(center.alerts) == 1


def test_alert_center_multi():
    center = AlertCenter()

    center.push({"level": "WARNING", "message": "test1"})
    center.push({"level": "CRITICAL", "message": "test2"})

    assert len(center.alerts) == 2


def test_observability_service():
    dashboard = DataDashboard()
    alert_center = AlertCenter()
    service = ObservabilityService(dashboard, alert_center)

    assert service.dashboard == dashboard
    assert service.alert_center == alert_center