"""Built-in incident detectors — default rule sets per domain signal.

Detectors only OWN rules; they never run detection themselves. The rules are
registered into a DetectionRegistry and evaluated by IncidentDetectionEngine.
"""

from __future__ import annotations

from typing import List

from ..detection.detection_registry import DetectionRegistry
from ..detection.detection_rule import DetectionRule
from .event_bus_detector import EventBusDetector
from .execution_detector import ExecutionDetector
from .health_detector import HealthDetector
from .ledger_detector import LedgerDetector
from .position_detector import PositionDetector
from .reconciliation_detector import ReconciliationDetector
from .recovery_detector import RecoveryDetector
from .risk_detector import RiskDetector

ALL_DETECTORS = (
    EventBusDetector,
    ExecutionDetector,
    HealthDetector,
    LedgerDetector,
    PositionDetector,
    ReconciliationDetector,
    RecoveryDetector,
    RiskDetector,
)


def register_default_rules(registry: DetectionRegistry) -> int:
    """Register every built-in detector's rules; returns the rule count."""
    count = 0
    for detector in ALL_DETECTORS:
        for rule in detector.build_rules():
            registry.register(rule)
            count += 1
    return count


__all__ = [
    "ALL_DETECTORS",
    "EventBusDetector",
    "ExecutionDetector",
    "HealthDetector",
    "LedgerDetector",
    "PositionDetector",
    "ReconciliationDetector",
    "RecoveryDetector",
    "RiskDetector",
    "register_default_rules",
]
