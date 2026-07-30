from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TelemetryEvent:
    event_type: str
    source: str
    data: Dict
    timestamp: datetime = field(default_factory=datetime.now)
    trace_id: Optional[str] = None


class TelemetryPipeline:
    def __init__(self):
        self._processors: Dict[str, List] = {
            "tracing": [],
            "metrics": [],
            "logging": [],
            "alerting": [],
        }
        self._events: List[TelemetryEvent] = []
        self._event_count: Dict[str, int] = {}

    def register_processor(self, event_type: str, processor):
        if event_type not in self._processors:
            self._processors[event_type] = []
        self._processors[event_type].append(processor)

    def emit(self, event: TelemetryEvent):
        self._events.append(event)
        count = self._event_count.get(event.event_type, 0)
        self._event_count[event.event_type] = count + 1

        processors = self._processors.get(event.event_type, [])
        for processor in processors:
            try:
                processor(event)
            except Exception:
                pass

    def emit_tracing_event(self, source: str, data: Dict, trace_id: Optional[str] = None):
        event = TelemetryEvent(
            event_type="tracing",
            source=source,
            data=data,
            trace_id=trace_id,
        )
        self.emit(event)

    def emit_metrics_event(self, source: str, data: Dict):
        event = TelemetryEvent(
            event_type="metrics",
            source=source,
            data=data,
        )
        self.emit(event)

    def emit_logging_event(self, source: str, data: Dict):
        event = TelemetryEvent(
            event_type="logging",
            source=source,
            data=data,
        )
        self.emit(event)

    def emit_alerting_event(self, source: str, data: Dict):
        event = TelemetryEvent(
            event_type="alerting",
            source=source,
            data=data,
        )
        self.emit(event)

    def get_events(
        self,
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[TelemetryEvent]:
        results = self._events
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if source:
            results = [e for e in results if e.source == source]
        return sorted(results, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_event_counts(self) -> Dict[str, int]:
        return dict(self._event_count)

    def get_processors(self) -> Dict[str, int]:
        return {k: len(v) for k, v in self._processors.items()}

    def get_pipeline_status(self) -> Dict:
        return {
            "total_events": len(self._events),
            "event_counts": dict(self._event_count),
            "registered_processors": self.get_processors(),
            "timestamp": datetime.now().isoformat(),
        }

    def clear(self):
        self._events.clear()
        self._event_count.clear()
