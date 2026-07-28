from services.alerting import *


def test_alerting():

    service = AlertingService(
        AlertRepository(),
        AlertDispatcher()
    )

    alert = Alert(
        "ALT001",
        "High CPU",
        AlertLevel.WARNING,
        "NEW"
    )

    result = service.publish(alert)

    assert result.status == "DISPATCHED"
