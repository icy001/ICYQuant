from services.observability import (
    create_context,
    set_context,
    get_request_id,
    get_trace_id,
)


def test_trace_context():
    context = create_context()
    set_context(
        context
    )
    assert (
        get_request_id()
        ==
        context.request_id
    )
    assert (
        get_trace_id()
        ==
        context.trace_id
    )