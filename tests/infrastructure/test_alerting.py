from infrastructure.alerting import (
    Severity,
    Alert,
)


def test_alert():

    alert = Alert(

        "service-down",

        "order service unavailable",

        Severity.CRITICAL,

        "health-monitor"

    )


    assert alert.severity == "CRITICAL"