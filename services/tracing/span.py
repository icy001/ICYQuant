from dataclasses import dataclass


@dataclass
class Span:

    span_id: str
    trace_id: str
    service: str
    duration: int
