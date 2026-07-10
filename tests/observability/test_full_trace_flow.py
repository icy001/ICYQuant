"""
End-to-end observability flow test.
"""

from services.observability import (
    create_context,
    set_context,
    get_trace_id,
    create_correlation,
    set_correlation,
    get_correlation,
    create_audit_event,
    AuditStore,
    MetricsCollector,
    ErrorTracker,
)


def test_full_observability_flow():
    trace_context = create_context()
    set_context(
        trace_context
    )
    assert (
        get_trace_id()
        ==
        trace_context.trace_id
    )

    correlation = create_correlation(
        request_id=
        trace_context.request_id,
        trace_id=
        trace_context.trace_id,
        user_id=
        "trader001",
    )
    set_correlation(
        correlation
    )

    current = get_correlation()
    assert current is not None
    assert (
        current.trace_id
        ==
        trace_context.trace_id
    )

    audit = create_audit_event(
        action=
        "SUBMIT_ORDER",
        actor=
        "trader001",
        resource=
        "ORDER001",
    )

    assert (
        audit.trace_id
        ==
        trace_context.trace_id
    )
    assert (
        audit.correlation_id
        ==
        correlation.correlation_id
    )

    store = AuditStore()
    store.append(
        audit
    )
    assert (
        store.count()
        ==
        1
    )

    metrics = MetricsCollector()
    metrics.increment(
        "orders.submitted"
    )
    assert (
        metrics.get(
            "orders.submitted"
        )
        ==
        1
    )

    tracker = ErrorTracker()
    error = tracker.capture(
        ValueError(
            "simulation"
        )
    )
    assert error.error_id