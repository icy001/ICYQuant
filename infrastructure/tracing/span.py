"""
Trace span model.
"""

from dataclasses import dataclass


@dataclass
class Span:

    trace_id: str

    service: str

    operation: str

    duration: float = 0