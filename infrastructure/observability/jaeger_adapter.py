from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class JaegerSpan:
    trace_id: str
    span_id: str
    operation_name: str
    service_name: str
    start_time: int
    duration: int
    tags: Dict[str, str] = field(default_factory=dict)
    logs: List[Dict] = field(default_factory=list)
    references: List[Dict] = field(default_factory=list)


class JaegerAdapter:
    def __init__(self, url: str = "http://localhost:16686"):
        self.url = url
        self._spans: List[JaegerSpan] = []
        self._traces: Dict[str, List[JaegerSpan]] = {}

    def record_span(
        self,
        trace_id: str,
        span_id: str,
        operation: str,
        service: str,
        start_time: int,
        duration: int,
        tags: Optional[Dict[str, str]] = None,
    ):
        span = JaegerSpan(
            trace_id=trace_id,
            span_id=span_id,
            operation_name=operation,
            service_name=service,
            start_time=start_time,
            duration=duration,
            tags=tags or {},
        )
        self._spans.append(span)
        if trace_id not in self._traces:
            self._traces[trace_id] = []
        self._traces[trace_id].append(span)

    def get_trace(self, trace_id: str) -> List[JaegerSpan]:
        return self._traces.get(trace_id, [])

    def search_traces(
        self,
        service: Optional[str] = None,
        operation: Optional[str] = None,
        limit: int = 20,
    ) -> List[List[JaegerSpan]]:
        results = []
        for trace_id, spans in self._traces.items():
            if service and not any(s.service_name == service for s in spans):
                continue
            if operation and not any(s.operation_name == operation for s in spans):
                continue
            results.append(spans)
        return results[:limit]

    def get_service_names(self) -> List[str]:
        services = set()
        for span in self._spans:
            services.add(span.service_name)
        return sorted(list(services))

    def get_operations(self, service: str) -> List[str]:
        ops = set()
        for span in self._spans:
            if span.service_name == service:
                ops.add(span.operation_name)
        return sorted(list(ops))

    def get_trace_count(self) -> int:
        return len(self._traces)

    def get_span_count(self) -> int:
        return len(self._spans)

    def clear(self):
        self._spans.clear()
        self._traces.clear()
