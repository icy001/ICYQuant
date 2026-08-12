"""EscalationPolicy — per-severity escalation ladders."""
from __future__ import annotations

from services.control_plane.incident.escalation.level import EscalationLevel
from services.control_plane.incident.escalation.policy import (
    DEFAULT_ESCALATION_POLICIES,
)
from services.control_plane.incident.incident_severity import IncidentSeverity


class TestEscalationPolicy:
    def test_default_policies_cover_severities(self):
        assert set(DEFAULT_ESCALATION_POLICIES) == {
            IncidentSeverity.LOW,
            IncidentSeverity.MEDIUM,
            IncidentSeverity.HIGH,
            IncidentSeverity.CRITICAL,
        }

    def test_high_policy_ladder(self):
        policy = DEFAULT_ESCALATION_POLICIES[IncidentSeverity.HIGH]
        assert policy.initial_level == EscalationLevel.L2
        assert policy.max_level == EscalationLevel.L4
        assert policy.timeout_seconds == (300, 900)

    def test_critical_starts_high(self):
        policy = DEFAULT_ESCALATION_POLICIES[IncidentSeverity.CRITICAL]
        assert policy.initial_level == EscalationLevel.L3
        assert policy.max_level == EscalationLevel.L4
        assert policy.timeout_seconds == (60,)

    def test_low_never_leaves_l1_l2(self):
        policy = DEFAULT_ESCALATION_POLICIES[IncidentSeverity.LOW]
        assert policy.initial_level == EscalationLevel.L1
        assert policy.max_level == EscalationLevel.L2
        assert policy.timeout_seconds == (1800,)
