"""
CorrelationContext — normalized input for a correlation evaluation.

Wraps the DetectionResult plus evaluation metadata (the reference time and the
temporal window used to find active parents).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..detection.detection_result import DetectionResult


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class CorrelationContext:
    detection: DetectionResult
    now: datetime = field(default_factory=_utcnow)
    window_seconds: float = 300.0
