from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from uuid import uuid4
from datetime import datetime


class SpanStatus(Enum):
    OK = "OK"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


@dataclass
class Span:
    span_id: str
    trace_id: str
    operation: str
    service: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = SpanStatus.OK.value
    attributes: Dict[str, str] = field(default_factory=dict)
    parent_id: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return 0.0


@dataclass
class Trace:
    trace_id: str
    spans: List[Span] = field(default_factory=list)
    service: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def total_duration_ms(self) -> float:
        if self.spans:
            return max((s.duration_ms for s in self.spans), default=0.0)
        return 0.0

    @property
    def has_errors(self) -> bool:
        return any(s.status == SpanStatus.ERROR.value for s in self.spans)

    def get_span(self, span_id: str) -> Optional[Span]:
        for span in self.spans:
            if span.span_id == span_id:
                return span
        return None


class Tracer:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self._traces: Dict[str, Trace] = {}
        self._active_spans: Dict[str, Span] = {}

    def start_span(
        self,
        operation: str,
        trace_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        attributes: Optional[Dict[str, str]] = None,
    ) -> Span:
        tid = trace_id or uuid4().hex
        span = Span(
            span_id=uuid4().hex[:16],
            trace_id=tid,
            operation=operation,
            service=self.service_name,
            start_time=datetime.now(),
            parent_id=parent_id,
            attributes=attributes or {},
        )
        if tid not in self._traces:
            self._traces[tid] = Trace(trace_id=tid, service=self.service_name)
        self._traces[tid].spans.append(span)
        self._active_spans[span.span_id] = span
        return span

    def end_span(self, span_id: str, status: str = SpanStatus.OK.value):
        span = self._active_spans.pop(span_id, None)
        if span:
            span.end_time = datetime.now()
            span.status = status

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        return self._traces.get(trace_id)

    def get_all_traces(self) -> List[Trace]:
        return list(self._traces.values())

    def get_recent_traces(self, limit: int = 20) -> List[Trace]:
        traces = sorted(
            self._traces.values(),
            key=lambda t: t.start_time or datetime.min,
            reverse=True,
        )
        return traces[:limit]

    def clear(self):
        self._traces.clear()
        self._active_spans.clear()


class DistributedTracing:
    def __init__(self):
        self._tracers: Dict[str, Tracer] = {}

    def get_tracer(self, service_name: str) -> Tracer:
        if service_name not in self._tracers:
            self._tracers[service_name] = Tracer(service_name)
        return self._tracers[service_name]

    def new_trace_id(self) -> str:
        return uuid4().hex

    def inject_context(self, trace_id: str, span_id: str) -> Dict[str, str]:
        return {
            "X-Trace-ID": trace_id,
            "X-Span-ID": span_id,
        }

    def extract_context(self, headers: Dict[str, str]) -> Optional[Dict[str, str]]:
        trace_id = headers.get("X-Trace-ID")
        span_id = headers.get("X-Span-ID")
        if trace_id and span_id:
            return {"trace_id": trace_id, "span_id": span_id}
        return None

    def get_all_traces(self) -> List[Trace]:
        all_traces = []
        for tracer in self._tracers.values():
            all_traces.extend(tracer.get_all_traces())
        return all_traces
