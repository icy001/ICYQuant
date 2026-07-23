from infrastructure.tracing import (
    TraceIdGenerator,
)


def test_trace_id():

    generator = TraceIdGenerator()

    trace_id = generator.generate()

    assert trace_id is not None