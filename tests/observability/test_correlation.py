from services.observability import (
    create_correlation,
    set_correlation,
    get_correlation,
    update_order,
    update_event,
)


def test_create_correlation():
    context = create_correlation(
        request_id="req001",
        trace_id="trace001",
        user_id="user001",
    )
    set_correlation(
        context
    )
    current = get_correlation()
    assert current is not None
    assert (
        current.request_id
        ==
        "req001"
    )
    assert (
        current.trace_id
        ==
        "trace001"
    )


def test_order_event_binding():
    context = create_correlation()
    set_correlation(
        context
    )
    update_order(
        "order001"
    )
    update_event(
        "event001"
    )
    current = get_correlation()
    assert (
        current.order_id
        ==
        "order001"
    )
    assert (
        current.event_id
        ==
        "event001"
    )