"""LifecyclePolicy — per-severity handling windows."""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from services.control_plane.incident.incident_severity import IncidentSeverity
from services.control_plane.incident.lifecycle.policy import (
    DEFAULT_POLICIES,
    LifecyclePolicy,
    get_policy,
)


class TestLifecyclePolicy:
    def test_default_policies_cover_severities(self):
        assert set(DEFAULT_POLICIES) == {
            IncidentSeverity.LOW,
            IncidentSeverity.MEDIUM,
            IncidentSeverity.HIGH,
            IncidentSeverity.CRITICAL,
        }

    def test_high_policy_timeouts(self):
        policy = get_policy(IncidentSeverity.HIGH)
        assert isinstance(policy, LifecyclePolicy)
        assert policy.acknowledge_timeout_seconds == 300
        assert policy.mitigation_timeout_seconds == 900
        assert policy.resolution_timeout_seconds == 3600
        assert policy.auto_escalate is True

    def test_critical_has_fastest_windows(self):
        critical = get_policy(IncidentSeverity.CRITICAL)
        low = get_policy(IncidentSeverity.LOW)
        assert critical.acknowledge_timeout_seconds < low.acknowledge_timeout_seconds
        assert critical.mitigation_timeout_seconds < low.mitigation_timeout_seconds
        assert critical.resolution_timeout_seconds < low.resolution_timeout_seconds

    def test_policy_is_frozen(self):
        policy = get_policy(IncidentSeverity.LOW)
        with pytest.raises(FrozenInstanceError):
            policy.acknowledge_timeout_seconds = 1
