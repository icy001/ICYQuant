"""Built-in incident correlators — declarative causal relationships.

Correlators only OWN rules; CorrelationEngine applies them to decide whether a
detection becomes a child of an active parent incident.
"""

from __future__ import annotations

from typing import List

from ..correlation.correlation_rule import CorrelationRule
from .execution_correlator import ExecutionCorrelator
from .health_correlator import HealthCorrelator
from .integrity_correlator import IntegrityCorrelator
from .recovery_correlator import RecoveryCorrelator
from .risk_correlator import RiskCorrelator
from .root_cause_correlator import RootCauseCorrelator

ALL_CORRELATORS = (
    ExecutionCorrelator,
    HealthCorrelator,
    IntegrityCorrelator,
    RecoveryCorrelator,
    RiskCorrelator,
    RootCauseCorrelator,
)


def build_default_rules() -> List[CorrelationRule]:
    """Collect every built-in correlator's rules into one list."""
    rules: List[CorrelationRule] = []
    for correlator in ALL_CORRELATORS:
        rules.extend(correlator.build_rules())
    return rules


__all__ = [
    "ALL_CORRELATORS",
    "ExecutionCorrelator",
    "HealthCorrelator",
    "IntegrityCorrelator",
    "RecoveryCorrelator",
    "RiskCorrelator",
    "RootCauseCorrelator",
    "build_default_rules",
]
