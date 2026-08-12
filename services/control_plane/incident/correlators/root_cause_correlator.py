"""
RootCauseCorrelator — identifies the root cause incident within a cluster.

Heuristics (spec section 37):

1. The EARLIEST opened incident is the most likely root cause.
2. Ties are broken by out-degree: the incident referenced as a parent by the
   most other incidents wins.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from ..correlation.correlation_rule import CorrelationRule
from ..incident import Incident
from ..incident_type import IncidentType


class RootCauseCorrelator:
    """Ranks a group of incidents and picks the root cause."""

    RULES: List[CorrelationRule] = [
        CorrelationRule(
            rule_id="ROOT-CAUSE-HEALTH-001",
            parent_incident_type=IncidentType.HEALTH_FAILURE,
            child_incident_type=IncidentType.SYSTEM_FAILURE,
            max_window_seconds=900.0,
            confidence=0.95,
            priority=10,
            description="unattributed system failures inherit health parents",
        ),
    ]

    @classmethod
    def build_rules(cls) -> List[CorrelationRule]:
        return list(cls.RULES)

    @staticmethod
    def find_root_cause(
        incidents: Sequence[Incident],
    ) -> Optional[Incident]:
        """Return the root cause incident of the group, or None if empty.

        Earliest-created wins; ties broken by the number of other incidents
        that reference it as a parent.
        """
        incidents = list(incidents)
        if not incidents:
            return None

        def _out_degree(inc: Incident) -> int:
            ref = inc.incident_id.value
            return sum(
                1 for other in incidents if other.parent_incident_id == ref
            )

        def _key(inc: Incident):
            return (inc.created_at, -_out_degree(inc))

        return min(incidents, key=_key)

    @staticmethod
    def promote_root_cause(
        incidents: Sequence[Incident], root: Incident
    ) -> None:
        """Reparent a group so that ``root`` becomes the root cause.

        Root Cause Promotion (spec section 35): when a deeper cause is
        discovered, the previous root is demoted to a child instead of being
        silently relabelled.  Only incidents in ``incidents`` are touched.
        """
        root_id = root.incident_id.value
        children: List[str] = []
        for incident in incidents:
            if incident.incident_id.value == root_id:
                incident.parent_incident_id = None
                incident.root_cause_incident_id = None
            else:
                incident.parent_incident_id = root_id
                incident.root_cause_incident_id = root_id
                children.append(incident.incident_id.value)
        root.child_incident_ids = children
