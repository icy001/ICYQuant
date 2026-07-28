from dataclasses import dataclass


@dataclass
class Span:

    span_id: str

    service: str

    duration: float
