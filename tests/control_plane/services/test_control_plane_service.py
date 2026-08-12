"""Unit tests: ControlPlaneService — lifecycle, heartbeat, evaluation, control actions, snapshot."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.control_plane.domain.component_registry import ComponentType
from services.control_plane.domain.component_state import ComponentState
from services.control_plane.domain.operational_state import OperationalState
from services.control_plane.domain.system_state import (
    StateReasonCode,
    StateTransitionError,
    SystemState,
)
from services.control_plane.domain.trading_gate import GateDecision, RiskIntegrity
from services.control_plane.domain.trading_state import TradingState
from services.control_plane.services.control_plane_service import ControlPlaneService

NOW = datetime.now(timezone.utc)


def _boot_healthy_service() -> ControlPlaneService:
    """A fully started service: all components registered, healthy, system READY."""
    service = ControlPlaneService(heartbeat_timeout_ms=15000)
    service.register_default_components()
    # non-critical component used to prove that its failure never blocks trading
    service.register_component("analytics", ComponentType.ANALYTICS, version="1.0.0")
    for info in service._registry.list_components():
        info.update_state(ComponentState.HEALTHY, NOW)
        info.mark_heartbeat(NOW)
        service.repository.save_component(info)
    service.start()
    service.complete_startup()
    service.collect_events()
    return service


# ============================================================
# Startup lifecycle
# ============================================================

class TestStartupLifecycle:
    def test_initial_state(self):
        service = ControlPlaneService()
        assert service.get_state() == {
            "system": "INITIALIZING",
            "trading": "TRADING_DISABLED",
            "operational": "NORMAL",
        }

    def test_start_transitions_to_starting(self):
        service = ControlPlaneService()
        service.start()
        assert service._system_state is SystemState.STARTING
        events = service.collect_events()
        assert any(e.event_type == "SYSTEM_STATE_CHANGED" for e in events)
        assert events[0].previous_state is SystemState.INITIALIZING
        assert events[0].new_state is SystemState.STARTING

    def test_complete_startup_reaches_ready(self):
        service = _boot_healthy_service()
        assert service.get_state() == {
            "system": "READY",
            "trading": "TRADING_READY",
            "operational": "NORMAL",
        }
        assert service.can_trade()

    def test_complete_startup_without_starting_raises(self):
        service = ControlPlaneService()
        with pytest.raises(StateTransitionError):
            service.complete_startup()

    def test_complete_startup_requires_healthy_critical_components(self):
        service = ControlPlaneService()
        service.register_default_components()
        # risk engine never becomes healthy
        service.start()
        with pytest.raises(RuntimeError):
            service.complete_startup()

    def test_restart_after_fail(self):
        service = _boot_healthy_service()
        service.fail(StateReasonCode.COMPONENT_FAILED)
        assert service._system_state is SystemState.FAILED
        service.restart()
        assert service._system_state is SystemState.STARTING
        # complete the cycle again
        for info in service._registry.list_components():
            info.update_state(ComponentState.HEALTHY, NOW)
            info.mark_heartbeat(NOW)
        service.complete_startup()
        assert service._system_state is SystemState.READY


# ============================================================
# Component registration + heartbeat
# ============================================================

class TestComponentRegistrationAndHeartbeat:
    def test_register_default_components(self):
        service = ControlPlaneService()
        count = service.register_default_components()
        assert count == 9
        assert len(service.get_components()) == 9
        assert service.repository.component_count() == 9

    def test_register_custom_component(self):
        service = ControlPlaneService()
        service.register_component("dashboard", ComponentType.DASHBOARD, version="1.0.0")
        assert service._registry.has("dashboard")
        assert service.repository.get_component("dashboard") is not None

    def test_update_unknown_component_raises(self):
        service = ControlPlaneService()
        with pytest.raises(ValueError):
            service.update_component_state(
                "ghost", ComponentState.HEALTHY, StateReasonCode.SYSTEM_HEALTHY
            )

    def test_heartbeat_unknown_component_raises(self):
        service = ControlPlaneService()
        with pytest.raises(ValueError):
            service.heartbeat("ghost")

    def test_component_state_change_emits_event(self):
        service = _boot_healthy_service()
        result = service.update_component_state(
            "analytics", ComponentState.STOPPED, StateReasonCode.MAINTENANCE
        )
        assert result.changed
        events = service.collect_events()
        assert any(
            e.event_type == "COMPONENT_STATE_CHANGED"
            and e.component_id == "analytics"
            and e.previous_state is ComponentState.HEALTHY
            and e.new_state is ComponentState.STOPPED
            for e in events
        )

    def test_component_state_noop_no_event(self):
        service = _boot_healthy_service()
        result = service.update_component_state(
            "analytics", ComponentState.HEALTHY, StateReasonCode.SYSTEM_HEALTHY
        )
        assert not result.changed
        assert service.collect_events() == []

    def test_heartbeat_timeout_marks_unknown_and_blocks_trading(self):
        service = _boot_healthy_service()
        service.heartbeat("event_bus", NOW)
        timed_out = service.check_heartbeats(at=NOW + timedelta(seconds=20))
        assert "event_bus" in timed_out
        assert service._registry.get("event_bus").state is ComponentState.UNKNOWN
        # critical component went UNKNOWN → gate DENY
        assert service.get_trading_gate()["decision"] == "DENY"
        assert service.get_state()["trading"] == "TRADING_HALTED"

    def test_heartbeat_restores_unknown_component(self):
        service = _boot_healthy_service()
        service.check_heartbeats(at=NOW + timedelta(seconds=20))  # all UNKNOWN
        service.collect_events()
        assert service._registry.get("event_bus").state is ComponentState.UNKNOWN
        for info in service._registry.list_components():
            service.heartbeat(info.component_id, NOW + timedelta(seconds=30))
        assert service._registry.get("event_bus").state is ComponentState.HEALTHY
        assert service.get_trading_gate()["decision"] == "ALLOW"
        assert service.get_state()["trading"] == "TRADING_READY"

    def test_health_score_is_auxiliary(self):
        service = _boot_healthy_service()
        service.set_health_score("position_service", 40.0)
        assert service._registry.get("position_service").health_score == 40.0
        # score alone never blocks trading
        assert service.get_trading_gate()["decision"] == "ALLOW"


# ============================================================
# Evaluation — state derivation
# ============================================================

class TestEvaluation:
    def test_healthy_state(self):
        service = _boot_healthy_service()
        assert service.get_state()["system"] == "READY"
        assert service.get_trading_gate() == {"decision": "ALLOW", "reason": "SYSTEM_HEALTHY"}

    def test_degraded_state_position_mismatch(self):
        service = _boot_healthy_service()
        service.update_component_state(
            "position_service", ComponentState.DEGRADED, StateReasonCode.POSITION_MISMATCH
        )
        assert service.get_state() == {
            "system": "DEGRADED",
            "trading": "TRADING_DEGRADED",
            "operational": "DEGRADED",
        }
        assert service.get_trading_gate()["decision"] == "ALLOW"

    def test_recovering_state(self):
        service = _boot_healthy_service()
        service.update_component_state(
            "position_service", ComponentState.DEGRADED, StateReasonCode.POSITION_MISMATCH
        )
        service.update_component_state(
            "position_service",
            ComponentState.RECOVERING,
            StateReasonCode.POSITION_RECOVERY,
        )
        # single recovering component → system DEGRADED, operational RECOVERY
        assert service.get_state()["system"] == "DEGRADED"
        assert service.get_state()["operational"] == "RECOVERY"
        # recovery engine actively running → system RECOVERING
        service.evaluate(recovery_active=True)
        assert service.get_state()["system"] == "RECOVERING"

    def test_halted_state_critical_component(self):
        service = _boot_healthy_service()
        service.update_component_state(
            "risk_engine", ComponentState.UNHEALTHY, StateReasonCode.RISK_ENGINE_UNHEALTHY
        )
        assert service.get_state()["system"] == "HALTED"
        assert service.get_state()["trading"] == "TRADING_HALTED"
        assert service.get_trading_gate() == {
            "decision": "DENY",
            "reason": "RISK_ENGINE_UNHEALTHY",
        }
        assert not service.can_trade()

    def test_non_critical_component_keeps_trading_ready(self):
        service = _boot_healthy_service()
        service.update_component_state(
            "analytics", ComponentState.STOPPED, StateReasonCode.MAINTENANCE
        )
        # System degraded, but trading core path intact.
        assert service.get_state()["system"] == "DEGRADED"
        assert service.get_state()["trading"] == "TRADING_READY"
        assert service.get_state()["operational"] == "DEGRADED"
        assert service.can_trade()

    def test_failed_state(self):
        service = _boot_healthy_service()
        service.fail(StateReasonCode.COMPONENT_FAILED)
        assert service.get_state()["system"] == "FAILED"
        assert service.get_state()["trading"] == "TRADING_HALTED"

    def test_risk_integrity_untrusted_halts(self):
        service = _boot_healthy_service()
        service.set_risk_integrity(RiskIntegrity.UNTRUSTED)
        service.evaluate()
        assert service.get_state() == {
            "system": "HALTED",
            "trading": "TRADING_HALTED",
            "operational": "EMERGENCY",
        }
        assert service.get_trading_gate()["decision"] == "DENY"

    def test_risk_integrity_degraded_constrains_trading(self):
        service = _boot_healthy_service()
        service.set_risk_integrity(RiskIntegrity.DEGRADED)
        service.evaluate()
        assert service.get_state()["trading"] == "TRADING_DEGRADED"
        assert service.get_state()["system"] == "DEGRADED"
        assert service.get_state()["operational"] == "DEGRADED"
        assert service.can_trade()


# ============================================================
# Manual / Emergency halt
# ============================================================

class TestControlActions:
    def test_manual_halt_freezes_trading_keeps_system_ready(self):
        service = _boot_healthy_service()
        service.manual_halt()
        assert service.get_state()["system"] == "READY"
        assert service.get_state()["trading"] == "TRADING_HALTED"
        assert service.get_state()["operational"] == "HALT"
        assert not service.can_trade()

    def test_resume_after_manual_halt(self):
        service = _boot_healthy_service()
        service.manual_halt()
        service.resume()
        assert service.get_state()["trading"] == "TRADING_READY"
        assert service.can_trade()

    def test_manual_halt_emits_trading_state_event(self):
        service = _boot_healthy_service()
        service.manual_halt()
        events = service.collect_events()
        assert any(
            e.event_type == "TRADING_STATE_CHANGED"
            and e.previous_state is TradingState.TRADING_READY
            and e.new_state is TradingState.TRADING_HALTED
            and e.reason is StateReasonCode.MANUAL_HALT
            for e in events
        )

    def test_emergency_halt(self):
        service = _boot_healthy_service()
        service.emergency_halt()
        assert service.get_state() == {
            "system": "HALTED",
            "trading": "TRADING_HALTED",
            "operational": "EMERGENCY",
        }

    def test_maintenance_window(self):
        service = _boot_healthy_service()
        service.enter_maintenance()
        assert service.get_state()["system"] == "MAINTENANCE"
        assert service.get_state()["trading"] == "TRADING_HALTED"
        assert service.get_state()["operational"] == "MAINTENANCE"
        service.exit_maintenance()
        assert service.get_state()["system"] == "READY"
        assert service.get_state()["trading"] == "TRADING_READY"


# ============================================================
# Events
# ============================================================

class TestStateChangeEvents:
    def test_system_state_changed_event(self):
        service = _boot_healthy_service()
        service.update_component_state(
            "position_service", ComponentState.DEGRADED, StateReasonCode.POSITION_MISMATCH
        )
        events = service.collect_events()
        system_events = [e for e in events if e.event_type == "SYSTEM_STATE_CHANGED"]
        assert len(system_events) == 1
        event = system_events[0]
        assert event.previous_state is SystemState.READY
        assert event.new_state is SystemState.DEGRADED
        assert event.reason is StateReasonCode.POSITION_MISMATCH

    def test_trading_state_changed_event(self):
        service = _boot_healthy_service()
        service.update_component_state(
            "risk_engine", ComponentState.UNHEALTHY, StateReasonCode.RISK_ENGINE_UNHEALTHY
        )
        events = service.collect_events()
        trading_events = [e for e in events if e.event_type == "TRADING_STATE_CHANGED"]
        assert len(trading_events) == 1
        event = trading_events[0]
        assert event.previous_state is TradingState.TRADING_READY
        assert event.new_state is TradingState.TRADING_HALTED
        assert event.gate_decision == "DENY"

    def test_events_persisted_in_repository(self):
        service = _boot_healthy_service()
        service.update_component_state(
            "position_service", ComponentState.DEGRADED, StateReasonCode.POSITION_MISMATCH
        )
        event_types = {e["event_type"] for e in service.repository.get_events()}
        assert "COMPONENT_STATE_CHANGED" in event_types
        assert "SYSTEM_STATE_CHANGED" in event_types
        assert "TRADING_STATE_CHANGED" in event_types


# ============================================================
# API contract
# ============================================================

class TestApiContract:
    def test_state_contract(self):
        service = _boot_healthy_service()
        assert service.get_state() == {
            "system": "READY",
            "trading": "TRADING_READY",
            "operational": "NORMAL",
        }

    def test_components_contract(self):
        service = _boot_healthy_service()
        components = service.get_components()
        assert len(components) == 10  # 9 default + analytics
        first = components[0]
        for key in ("component_id", "component_type", "state", "health_score", "last_heartbeat_at"):
            assert key in first

    def test_trading_gate_contract(self):
        service = _boot_healthy_service()
        assert service.get_trading_gate() == {"decision": "ALLOW", "reason": "SYSTEM_HEALTHY"}


# ============================================================
# Snapshot
# ============================================================

class TestSnapshot:
    def test_snapshot_contains_full_view(self):
        service = _boot_healthy_service()
        service.update_component_state(
            "position_service", ComponentState.RECOVERING, StateReasonCode.POSITION_RECOVERY
        )
        snapshot = service.get_snapshot()
        assert snapshot.system_state is SystemState.DEGRADED
        assert snapshot.trading_state is TradingState.TRADING_DEGRADED
        assert snapshot.operational_state is OperationalState.RECOVERY
        assert snapshot.component_states["position_service"] == "RECOVERING"
        assert snapshot.trading_gate is not None
        assert snapshot.trading_gate.decision is GateDecision.ALLOW

    def test_snapshot_serialization_roundtrip(self):
        service = _boot_healthy_service()
        snapshot = service.get_snapshot()
        restored = service.repository.get_snapshot()
        assert restored.to_dict() == snapshot.to_dict()

    def test_rebuild_snapshot_from_event_log(self):
        service = _boot_healthy_service()
        # degrade, recover, restore — creates an event trail
        service.update_component_state(
            "position_service", ComponentState.DEGRADED, StateReasonCode.POSITION_MISMATCH
        )
        service.update_component_state(
            "position_service", ComponentState.HEALTHY, StateReasonCode.SYSTEM_HEALTHY
        )
        expected = service.get_snapshot()

        # snapshot is a projection — wipe it and rebuild from the event log
        service.repository.clear_snapshot()
        rebuilt = service.rebuild_snapshot()

        assert rebuilt.system_state is expected.system_state
        assert rebuilt.trading_state is expected.trading_state
        assert rebuilt.operational_state is expected.operational_state
        assert rebuilt.component_states == expected.component_states

    def test_rebuild_after_full_wipe(self):
        service = _boot_healthy_service()
        service.update_component_state(
            "ledger_service", ComponentState.DEGRADED, StateReasonCode.LEDGER_MISMATCH
        )
        expected_system = service.get_state()["system"]

        service.repository.clear_snapshot()
        service.repository.clear_components()
        rebuilt = service.rebuild_snapshot()

        assert rebuilt.system_state is SystemState(expected_system)
        assert rebuilt.component_states["ledger_service"] == "DEGRADED"
