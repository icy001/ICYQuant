from services.audit import *


def test_audit():
    store = AuditStore()
    repo = AuditRepository(store)
    service = AuditService(repo)

    event = AuditEvent(
        "AUD001",
        "ORDER_CREATED",
        "TRADER001",
        {
            "symbol": "NVDA"
        }
    )

    service.record(event)

    result = service.history()

    assert len(result) == 1
