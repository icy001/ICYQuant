from services.observability import (
    AuditStore,
    create_audit_event,
    create_correlation,
    set_correlation,
)


def test_audit_event_creation():
    context = create_correlation(
        trace_id="trace001"
    )
    set_correlation(
        context
    )
    event = create_audit_event(
        action="CREATE_ORDER",
        actor="user001",
        resource="ORDER",
    )
    assert (
        event.action
        ==
        "CREATE_ORDER"
    )
    assert (
        event.trace_id
        ==
        "trace001"
    )


def test_audit_store():
    store = AuditStore()
    event = create_audit_event(
        action="LOGIN",
        actor="admin",
        resource="SYSTEM",
    )
    store.append(
        event
    )
    assert (
        store.count()
        ==
        1
    )