from services.observability import (
    DistributedTracing,
    Tracer,
    Span,
    Trace,
    SpanStatus,
)


class TestSpan:
    def test_span_creation(self):
        span = Span(
            span_id="span1",
            trace_id="trace1",
            operation="test_op",
            service="test_svc",
            start_time=None,
        )
        assert span.span_id == "span1"
        assert span.trace_id == "trace1"

    def test_span_duration(self):
        from datetime import datetime, timedelta
        start = datetime.now()
        end = start + timedelta(milliseconds=150)
        span = Span(
            span_id="span1",
            trace_id="trace1",
            operation="test_op",
            service="test_svc",
            start_time=start,
            end_time=end,
        )
        assert abs(span.duration_ms - 150) < 1


class TestTracer:
    def test_start_span(self):
        tracer = Tracer("test_service")
        span = tracer.start_span("test_operation")
        assert span.span_id is not None
        assert span.trace_id is not None
        assert span.service == "test_service"
        assert span.operation == "test_operation"

    def test_end_span(self):
        tracer = Tracer("test_service")
        span = tracer.start_span("test_op")
        tracer.end_span(span.span_id, SpanStatus.OK.value)
        trace = tracer.get_trace(span.trace_id)
        assert trace is not None
        assert len(trace.spans) == 1
        assert trace.spans[0].end_time is not None

    def test_trace_with_multiple_spans(self):
        tracer = Tracer("test_service")
        span1 = tracer.start_span("op1")
        span2 = tracer.start_span("op2", trace_id=span1.trace_id, parent_id=span1.span_id)
        tracer.end_span(span1.span_id)
        tracer.end_span(span2.span_id)
        trace = tracer.get_trace(span1.trace_id)
        assert len(trace.spans) == 2

    def test_get_recent_traces(self):
        tracer = Tracer("test_service")
        for i in range(5):
            span = tracer.start_span(f"op_{i}")
            tracer.end_span(span.span_id)
        recent = tracer.get_recent_traces(limit=3)
        assert len(recent) == 3

    def test_clear(self):
        tracer = Tracer("test_service")
        span = tracer.start_span("test_op")
        tracer.end_span(span.span_id)
        tracer.clear()
        assert len(tracer.get_all_traces()) == 0


class TestDistributedTracing:
    def test_get_tracer(self):
        dt = DistributedTracing()
        t1 = dt.get_tracer("service_a")
        t2 = dt.get_tracer("service_a")
        assert t1 is t2

    def test_new_trace_id(self):
        dt = DistributedTracing()
        tid = dt.new_trace_id()
        assert len(tid) > 0

    def test_inject_extract_context(self):
        dt = DistributedTracing()
        tid = dt.new_trace_id()
        headers = dt.inject_context(tid, "span1")
        assert "X-Trace-ID" in headers
        assert headers["X-Trace-ID"] == tid

        context = dt.extract_context(headers)
        assert context is not None
        assert context["trace_id"] == tid

    def test_propagation_across_services(self):
        dt = DistributedTracing()
        t1 = dt.get_tracer("api_gateway")
        t2 = dt.get_tracer("risk_engine")

        span1 = t1.start_span("check_risk")
        headers = dt.inject_context(span1.trace_id, span1.span_id)

        context = dt.extract_context(headers)
        span2 = t2.start_span(
            "evaluate_risk",
            trace_id=context["trace_id"],
            parent_id=context["span_id"],
        )
        t1.end_span(span1.span_id)
        t2.end_span(span2.span_id)

        all_traces = dt.get_all_traces()
        assert len(all_traces) >= 2
