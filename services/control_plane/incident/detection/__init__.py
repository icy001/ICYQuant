"""Incident Detection — rules, registry and engine that turn events into detections."""

from .detection_context import DetectionContext
from .detection_engine import IncidentDetectionEngine
from .detection_registry import DetectionRegistry
from .detection_result import DetectionResult
from .detection_rule import DetectionRule, field_equals, field_in

__all__ = [
    "DetectionContext",
    "DetectionRegistry",
    "DetectionResult",
    "DetectionRule",
    "IncidentDetectionEngine",
    "field_equals",
    "field_in",
]
