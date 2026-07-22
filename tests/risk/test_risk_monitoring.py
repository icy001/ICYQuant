from services.risk import (
    RiskThreshold,
    RiskAlertEngine,
    RealTimeRiskMonitor,
)


def test_risk_monitoring():
    monitor = RealTimeRiskMonitor(
        RiskAlertEngine(),
    )

    level = monitor.check(
        0.85,
        RiskThreshold(
            "VAR",
            0.70,
            0.90,
        ),
    )

    assert level == "WARNING"