"""Incident Escalation — levels, policies and decisions.

NOTE: ``IncidentEscalationEngine`` is intentionally NOT re-exported here to
avoid an import cycle (it imports the lifecycle service, which imports the
``Incident`` aggregate — and the aggregate imports ``EscalationLevel`` from
this package). Import it directly from ``.engine`` instead.
"""

from .decision import EscalationDecision
from .level import EscalationLevel
from .policy import DEFAULT_ESCALATION_POLICIES, EscalationPolicy

__all__ = [
    "DEFAULT_ESCALATION_POLICIES",
    "EscalationDecision",
    "EscalationLevel",
    "EscalationPolicy",
]
