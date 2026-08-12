"""Incident Correlation — deciding what a detection means for incidents.

A detection is anomalous, but is it a new incident, an update of an existing
one, or a child of an active parent? The Correlation Engine answers that.
"""

from .correlation_context import CorrelationContext
from .correlation_engine import CorrelationEngine
from .correlation_result import CorrelationDecision, CorrelationResult
from .correlation_rule import CorrelationRule
from .fingerprint_builder import FingerprintBuilder
from .incident_cluster import IncidentCluster

__all__ = [
    "CorrelationContext",
    "CorrelationEngine",
    "CorrelationResult",
    "CorrelationDecision",
    "CorrelationRule",
    "FingerprintBuilder",
    "IncidentCluster",
]
