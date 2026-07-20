"""
Research event model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchEvent:
    event_type: str
    aggregate_id: str
    payload: dict