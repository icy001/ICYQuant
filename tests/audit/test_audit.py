from services.audit import *


def test_audit_service():
    service = AuditLoggingService(
        AuditManager(
            AuditRepository(),
            AuditValidator(),
            AuditRecorder()
        )
    )

    event = AuditEvent(
        "AUD001",
        "USER001",
        "CREATE_ORDER",
        "NVDA_ORDER",
        1000,
        "SUCCESS"
    )

    result = service.record(event)

    assert result.action == "CREATE_ORDER"

    assert len(service.history()) == 1