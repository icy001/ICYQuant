"""Tests for the mitigation policy (spec section 10)."""
from __future__ import annotations

from services.control_plane.incident.incident_severity import IncidentSeverity
from services.control_plane.incident.mitigation.action_type import (
    MitigationActionType,
)
from services.control_plane.incident.mitigation.policy import (
    DEFAULT_MITIGATION_POLICIES,
    MitigationPolicy,
)


def test_low_severity_pauses_strategy_only():
    policy = DEFAULT_MITIGATION_POLICIES[IncidentSeverity.LOW]

    assert policy.actions == (MitigationActionType.PAUSE_STRATEGY,)
    assert policy.automatic is True
    assert policy.approval_required is False


def test_medium_severity_cancels_orders_and_pauses():
    policy = DEFAULT_MITIGATION_POLICIES[IncidentSeverity.MEDIUM]

    assert MitigationActionType.CANCEL_OPEN_ORDERS in policy.actions
    assert MitigationActionType.PAUSE_STRATEGY in policy.actions


def test_high_severity_requires_approval():
    policy = DEFAULT_MITIGATION_POLICIES[IncidentSeverity.HIGH]

    assert policy.approval_required is True
    assert MitigationActionType.CANCEL_OPEN_ORDERS in policy.actions
    assert MitigationActionType.BLOCK_NEW_ORDERS in policy.actions
    assert MitigationActionType.REDUCE_RISK_LIMIT in policy.actions


def test_critical_severity_disables_strategy_and_execution():
    policy = DEFAULT_MITIGATION_POLICIES[IncidentSeverity.CRITICAL]

    assert policy.approval_required is True
    assert MitigationActionType.CANCEL_OPEN_ORDERS in policy.actions
    assert MitigationActionType.BLOCK_NEW_ORDERS in policy.actions
    assert MitigationActionType.DISABLE_STRATEGY in policy.actions
    assert MitigationActionType.DISABLE_EXECUTION in policy.actions


def test_fatal_severity_includes_kill_switch():
    policy = DEFAULT_MITIGATION_POLICIES[IncidentSeverity.FATAL]

    assert MitigationActionType.KILL_SWITCH in policy.actions
    assert policy.approval_required is True


def test_every_severity_has_a_policy():
    for severity in IncidentSeverity:
        assert isinstance(
            DEFAULT_MITIGATION_POLICIES[severity],
            MitigationPolicy,
        ), severity
