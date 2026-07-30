from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class OTelSpan:
    trace_id: str
    span_id: str
    name: str
    service_name: str
    start_time: str
    end_time: Optional[str] = None
    status: str = "OK"
    attributes: Dict[str, str] = field(default_factory=dict)
    parent_span_id: Optional[str] = None


class OTelCollector:
    def __init__(self, endpoint: str = "http://localhost:4317"):
        self.endpoint = endpoint
        self._spans: List[OTelSpan] = []
        self._traces: Dict[str, List[OTelSpan]] = {}

    def export_span(self, span: OTelSpan):
        self._spans.append(span)
        if span.trace_id not in self._traces:
            self._traces[span.trace_id] = []
        self._traces[span.trace_id].append(span)

    def export_spans(self, spans: List[OTelSpan]):
        for span in spans:
            self.export_span(span)

    def get_trace(self, trace_id: str) -> List[OTelSpan]:
        return self._traces.get(trace_id, [])

    def get_all_traces(self) -> Dict[str, List[OTelSpan]]:
        return dict(self._traces)

    def get_recent_spans(self, limit: int = 100) -> List[OTelSpan]:
        return sorted(self._spans, key=lambda s: s.start_time, reverse=True)[:limit]

    def export_to_otel(self) -> Dict:
        return {
            "endpoint": self.endpoint,
            "spans_count": len(self._spans),
            "traces_count": len(self._traces),
            "exported_at": datetime.now().isoformat(),
        }

    def clear(self):
        self._spans.clear()
        self._traces.clear()
