from services.tracing import *


def test_tracing():

    service = TracingService(
        TraceRepository(),
        SpanCollector()
    )

    trace = service.create_trace(
        Trace(
            "TRACE001",
            "ORDER_EXECUTION",
            "RUNNING"
        )
    )

    span = service.add_span(
        Span(
            "SPAN001",
            trace.trace_id,
            "RISK_SERVICE",
            120
        )
    )

    assert span.duration == 120
