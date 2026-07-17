from services.data.monitoring import (
    AnomalyDetector,
    DataMonitor,
    DriftDetector,
    QualityMetric,
    Alert,
    MonitoringService,
)


def test_anomaly():
    detector = AnomalyDetector()

    result = detector.detect(20, 10)

    assert result is True


def test_anomaly_no_detection():
    detector = AnomalyDetector()

    result = detector.detect(5, 10)

    assert result is False


def test_data_monitor():
    monitor = DataMonitor()

    metrics = monitor.collect([1, 2, 3, 4, 5])

    assert metrics["rows"] == 5


def test_drift_detector():
    detector = DriftDetector()

    result = detector.compare(100, 90)

    assert result is True


def test_drift_no_change():
    detector = DriftDetector()

    result = detector.compare(100, 100)

    assert result is False


def test_quality_metric():
    metric = QualityMetric(
        name="null_rate",
        value=0.01,
        status="PASS",
    )

    assert metric.name == "null_rate"
    assert metric.status == "PASS"


def test_alert():
    alert = Alert(
        level="WARNING",
        message="Price spike detected",
    )

    assert alert.level == "WARNING"
    assert alert.message == "Price spike detected"


def test_monitoring_service():
    monitor = DataMonitor()
    detector = AnomalyDetector()
    service = MonitoringService(monitor, detector)

    assert service.monitor == monitor
    assert service.detector == detector