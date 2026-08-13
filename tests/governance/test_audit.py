"""Tests for services.governance.audit (Commit 28 Part 1.1)."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from services.governance.audit import GovernanceAuditEvent


def test_governance_audit():
    """Spec section 35 — audit event captures the full governance chain."""
    event = GovernanceAuditEvent(
        event_id="AUD-001",
        timestamp=datetime.now(timezone.utc),
        principal_id="ops-001",
        resource="trading",
        action="pause",
        effect="ALLOW",
        reason="approved recovery",
        policy_id="POLICY-001",
        incident_id="INC-001",
        approval_id="APR-001",
    )

    assert event.incident_id == "INC-001"
    assert event.approval_id == "APR-001"
    assert event.event_id == "AUD-001"
    assert event.principal_id == "ops-001"
    assert event.resource == "trading"
    assert event.action == "pause"
    assert event.effect == "ALLOW"
    assert event.reason == "approved recovery"
    assert event.policy_id == "POLICY-001"


def test_governance_audit_defaults():
    event = GovernanceAuditEvent(
        event_id="AUD-002",
        timestamp=datetime.now(timezone.utc),
        principal_id="ops-001",
        resource="trading",
        action="resume",
        effect="DENY",
        reason="no policy matched",
    )

    assert event.policy_id is None
    assert event.incident_id is None
    assert event.approval_id is None


def test_governance_audit_is_frozen():
    event = GovernanceAuditEvent(
        event_id="AUD-001",
        timestamp=datetime.now(timezone.utc),
        principal_id="ops-001",
        resource="trading",
        action="pause",
        effect="ALLOW",
        reason="approved recovery",
    )
    with pytest.raises(FrozenInstanceError):
        event.effect = "DENY"  # type: ignore[misc]
