"""Unit tests: KillSwitch — activation, state, idempotency, auto-activation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.control_plane.health.health_status import HealthStatus
from services.control_plane.kill_switch.kill_switch import (
    KillSwitch,
    KillSwitchActivationOutcome,
    KillSwitchReleaseOutcome,
)
from services.control_plane.kill_switch.kill_switch_reason import KillSwitchReason
from services.control_plane.kill_switch.kill_switch_scope import KillSwitchScope
from services.control_plane.kill_switch.kill_switch_state import KillSwitchState

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


class TestActivation:
    def test_activate_global(self):
        ks = KillSwitch()
        result = ks.activate(
            scope=KillSwitchScope.GLOBAL,
            reason=KillSwitchReason.EMERGENCY,
            actor="operator-001",
            now=NOW,
        )
        assert result.outcome is KillSwitchActivationOutcome.ACTIVATED
        assert result.entry.state is KillSwitchState.ACTIVE
        assert result.entry.activated_at == NOW
        assert result.event is not None
        assert result.event.event_type == "KILL_SWITCH_ACTIVATED"

    def test_activate_scoped(self):
        ks = KillSwitch()
        result = ks.activate(
            scope=KillSwitchScope.STRATEGY,
            scope_id="ALPHA",
            reason=KillSwitchReason.EMERGENCY,
            actor="operator-001",
            now=NOW,
        )
        assert result.outcome is KillSwitchActivationOutcome.ACTIVATED
        assert result.entry.scope_id == "ALPHA"

    def test_activation_is_idempotent(self):
        ks = KillSwitch()
        ks.activate(
            scope=KillSwitchScope.GLOBAL,
            reason=KillSwitchReason.EMERGENCY,
            actor="operator-001",
            now=NOW,
        )
        second = ks.activate(
            scope=KillSwitchScope.GLOBAL,
            reason=KillSwitchReason.RISK_SYSTEM_FAILURE,
            actor="auto-kill-policy",
            now=NOW,
        )
        assert second.outcome is KillSwitchActivationOutcome.ALREADY_ACTIVE
        assert second.event is None
        assert ks.count() == 1

    def test_concurrent_activation_deduplicates(self):
        ks = KillSwitch()
        results = [
            ks.activate(
                scope=KillSwitchScope.GLOBAL,
                reason=KillSwitchReason.RISK_SYSTEM_FAILURE,
                actor="risk-monitor",
                now=NOW,
            ),
            ks.activate(
                scope=KillSwitchScope.GLOBAL,
                reason=KillSwitchReason.EVENT_BUS_CRITICAL_FAILURE,
                actor="event-monitor",
                now=NOW,
            ),
            ks.activate(
                scope=KillSwitchScope.GLOBAL,
                reason=KillSwitchReason.EXECUTION_ENGINE_CRITICAL_FAILURE,
                actor="exec-monitor",
                now=NOW,
            ),
        ]
        assert [r.outcome for r in results] == [
            KillSwitchActivationOutcome.ACTIVATED,
            KillSwitchActivationOutcome.ALREADY_ACTIVE,
            KillSwitchActivationOutcome.ALREADY_ACTIVE,
        ]
        assert len(ks.list_active()) == 1

    def test_requires_reason(self):
        ks = KillSwitch()
        with pytest.raises(ValueError, match="reason"):
            ks.activate(
                scope=KillSwitchScope.GLOBAL, reason=None, actor="operator-001"
            )

    def test_requires_actor(self):
        ks = KillSwitch()
        with pytest.raises(ValueError, match="actor"):
            ks.activate(
                scope=KillSwitchScope.GLOBAL,
                reason=KillSwitchReason.EMERGENCY,
                actor="",
            )

    def test_requires_scope(self):
        ks = KillSwitch()
        with pytest.raises(ValueError, match="scope"):
            ks.activate(scope=None, reason=KillSwitchReason.EMERGENCY, actor="op")

    def test_global_cannot_have_scope_id(self):
        ks = KillSwitch()
        with pytest.raises(ValueError, match="GLOBAL"):
            ks.activate(
                scope=KillSwitchScope.GLOBAL,
                scope_id="ACCT-1",
                reason=KillSwitchReason.EMERGENCY,
                actor="op",
            )

    def test_scoped_requires_scope_id(self):
        ks = KillSwitch()
        with pytest.raises(ValueError, match="scope_id"):
            ks.activate(
                scope=KillSwitchScope.ACCOUNT,
                reason=KillSwitchReason.EMERGENCY,
                actor="op",
            )


class TestState:
    def test_has_active(self):
        ks = KillSwitch()
        ks.activate(
            scope=KillSwitchScope.GLOBAL,
            reason=KillSwitchReason.EMERGENCY,
            actor="op",
            now=NOW,
        )
        assert ks.has_active(KillSwitchScope.GLOBAL) is True

    def test_list_active(self):
        ks = KillSwitch()
        ks.activate(
            scope=KillSwitchScope.STRATEGY,
            scope_id="ALPHA",
            reason=KillSwitchReason.EMERGENCY,
            actor="op",
            now=NOW,
        )
        active = ks.list_active()
        assert len(active) == 1
        assert active[0].scope is KillSwitchScope.STRATEGY

    def test_armed_then_activate(self):
        ks = KillSwitch()
        ks.activate(
            scope=KillSwitchScope.GLOBAL,
            reason=KillSwitchReason.EMERGENCY,
            actor="op",
            now=NOW,
        )
        assert ks.get(KillSwitchScope.GLOBAL).state is KillSwitchState.ACTIVE

    def test_trading_halt_not_system_shutdown(self):
        # Activation only blocks trading; the kill switch object keeps serving.
        ks = KillSwitch()
        ks.activate(
            scope=KillSwitchScope.GLOBAL,
            reason=KillSwitchReason.EMERGENCY,
            actor="op",
            now=NOW,
        )
        assert ks.has_active(KillSwitchScope.GLOBAL)
        assert ks.list_active()
        # The switch remains queryable and releasable — system keeps running.
        result = ks.request_release(KillSwitchScope.GLOBAL, actor="op", now=NOW)
        assert result.outcome is KillSwitchReleaseOutcome.RELEASE_REQUESTED


class TestAutoActivation:
    def test_risk_engine_critical_failure(self):
        ks = KillSwitch()
        result = ks.auto_activate(
            component_health={"risk_engine": HealthStatus.UNHEALTHY},
            correlation_id="auto-1",
            now=NOW,
        )
        assert result is not None
        assert result.outcome is KillSwitchActivationOutcome.ACTIVATED
        assert result.entry.scope is KillSwitchScope.GLOBAL
        assert result.entry.reason is KillSwitchReason.RISK_SYSTEM_FAILURE
        assert result.entry.actor == "auto-kill-policy"

    def test_event_bus_critical_failure(self):
        ks = KillSwitch()
        result = ks.auto_activate(
            component_health={"event_bus": HealthStatus.UNHEALTHY},
            now=NOW,
        )
        assert result.entry.reason is KillSwitchReason.EVENT_BUS_CRITICAL_FAILURE

    def test_execution_engine_critical_failure(self):
        ks = KillSwitch()
        result = ks.auto_activate(
            component_health={"execution_engine": HealthStatus.UNHEALTHY},
            now=NOW,
        )
        assert result.entry.reason is KillSwitchReason.EXECUTION_ENGINE_CRITICAL_FAILURE

    def test_position_integrity_failure(self):
        ks = KillSwitch()
        result = ks.auto_activate(position_integrity_ok=False, now=NOW)
        assert result.entry.reason is KillSwitchReason.POSITION_INTEGRITY_FAILURE

    def test_reconciliation_failure(self):
        ks = KillSwitch()
        result = ks.auto_activate(reconciliation_ok=False, now=NOW)
        assert result.entry.reason is KillSwitchReason.RECONCILIATION_FAILURE

    def test_no_trigger(self):
        ks = KillSwitch()
        result = ks.auto_activate(
            component_health={"risk_engine": HealthStatus.HEALTHY},
            position_integrity_ok=True,
            reconciliation_ok=True,
            now=NOW,
        )
        assert result is None

    def test_priority_risk_over_reconciliation(self):
        ks = KillSwitch()
        result = ks.auto_activate(
            component_health={"risk_engine": HealthStatus.UNHEALTHY},
            reconciliation_ok=False,
            now=NOW,
        )
        assert result.entry.reason is KillSwitchReason.RISK_SYSTEM_FAILURE

    def test_auto_activation_deduplicates(self):
        ks = KillSwitch()
        ks.auto_activate(
            component_health={"risk_engine": HealthStatus.UNHEALTHY},
            now=NOW,
        )
        second = ks.auto_activate(
            component_health={"event_bus": HealthStatus.UNHEALTHY},
            now=NOW,
        )
        assert second.outcome is KillSwitchActivationOutcome.ALREADY_ACTIVE
        assert len(ks.list_active()) == 1


class TestLifecycleAudit:
    def test_entry_serialization_round_trip(self):
        ks = KillSwitch()
        result = ks.activate(
            scope=KillSwitchScope.STRATEGY,
            scope_id="ALPHA",
            reason=KillSwitchReason.EMERGENCY,
            actor="operator-001",
            correlation_id="corr-1",
            now=NOW,
        )
        restored = result.entry.from_dict(result.entry.to_dict())
        assert restored == result.entry
        assert restored.scope is KillSwitchScope.STRATEGY
        assert restored.scope_id == "ALPHA"
        assert restored.actor == "operator-001"
