"""Unit tests: GateDecision / GateSeverity / GateDecisionRecord snapshot."""

from __future__ import annotations

from datetime import datetime, timezone

from services.control_plane.trading_gate.gate_decision import (
    GateDecision,
    GateDecisionRecord,
    GateSeverity,
)
from services.control_plane.trading_gate.gate_reason import GateReason

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


class TestGateDecision:
    def test_strict_enum(self):
        assert GateDecision.ALLOW.value == "ALLOW"
        assert GateDecision.DENY.value == "DENY"
        assert list(GateDecision) == [GateDecision.ALLOW, GateDecision.DENY]

    def test_severity_levels(self):
        assert GateSeverity.INFO.value == "INFO"
        assert GateSeverity.WARNING.value == "WARNING"
        assert GateSeverity.CRITICAL.value == "CRITICAL"


class TestGateDecisionRecord:
    def test_allow_flags(self):
        record = GateDecisionRecord(
            decision=GateDecision.ALLOW,
            reason=GateReason.SYSTEM_HEALTHY,
            severity=GateSeverity.INFO,
            evaluated_at=NOW,
            policy_version="trading-policy-v1.3",
            correlation_id="corr-1",
        )
        assert record.is_allow is True
        assert record.is_deny is False
        assert record.policy_version == "trading-policy-v1.3"

    def test_deny_flags(self):
        record = GateDecisionRecord(
            decision=GateDecision.DENY,
            reason=GateReason.RISK_ENGINE_UNHEALTHY,
            severity=GateSeverity.CRITICAL,
            evaluated_at=NOW,
        )
        assert record.is_deny is True
        assert record.is_allow is False

    def test_snapshot_round_trip(self):
        record = GateDecisionRecord(
            decision=GateDecision.DENY,
            reason=GateReason.RISK_ENGINE_UNHEALTHY,
            severity=GateSeverity.CRITICAL,
            evaluated_at=NOW,
            policy_version="trading-policy-v1.3",
            correlation_id="corr-9",
            order_id="ORD-001",
            snapshot={
                "system_state": "READY",
                "risk_health": "UNHEALTHY",
                "kill_switch_state": "INACTIVE",
            },
        )
        restored = GateDecisionRecord.from_dict(record.to_dict())
        assert restored == record
        assert restored.snapshot["risk_health"] == "UNHEALTHY"

    def test_default_timestamp_is_utc(self):
        record = GateDecisionRecord(
            decision=GateDecision.ALLOW, reason=GateReason.SYSTEM_HEALTHY
        )
        assert record.evaluated_at.tzinfo is not None
