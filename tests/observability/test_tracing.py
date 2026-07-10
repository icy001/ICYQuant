from services.observability import (
    Tracer,
)


def test_create_span():
    tracer = Tracer(
        "test"
    )
    span = tracer.create_span(
        "operation"
    )
    assert span.trace_id
    assert span.span_id


def test_child_span():
    tracer = Tracer(
        "test"
    )
    parent = tracer.create_span(
        "parent"
    )
    child = tracer.create_span(
        "child",
        parent,
    )
    assert (
        child.trace_id
        ==
        parent.trace_id
    )
    assert (
        child.parent_id
        ==
        parent.span_id
    )