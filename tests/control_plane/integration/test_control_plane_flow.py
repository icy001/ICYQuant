"""Integration tests: the full Control Plane flow across the production lifecycle.

    boot → healthy → position degrades → recovery → restored
    → emergency halt → restart → manual halt → resume
    → snapshot projection → event replay → rebuild
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.control_plane import (
    ComponentState,
    ControlPlaneRepository,
    ControlPlaneService,
    RiskIntegrity,
    StateReasonCode,
    SystemState,
    TradingState,
)
from services.control_plane.events.component_state_changed import ComponentStateChanged
from services.control_plane.events.system_state_changed import SystemStateChanged
from services.control_plane.events.trading_state_changed import TradingStateChanged

NOW = datetime.now(timezone.utc)


def _start_healthy_service() -> ControlPlaneService:
    """
    Boot the control plane to READY with every component healthy.

    State changes go through ``update_component_state`` so the event log is a
    complete, self-sufficient source of truth (required by the replay tests).
    """
    service = ControlPlaneService(heartbeat_timeout_ms=15000)
    service.register_default_components()
    service.start()
    for info in service._registry.list_components():
        service.update_component_state(
            info.component_id, ComponentState.HEALTHY, StateReasonCode.SYSTEM_HEALTHY
        )
        service.heartbeat(info.component_id, NOW)
    service.complete_startup()
    service.collect_events()
    return service


class TestFullLifecycleFlow:
    def test_boot_to_ready(self):
        service = _start_healthy_service()
        assert service.get_state() == {
            "system": "READY",
            "trading": "TRADING_READY",
            "operational": "NORMAL",
        }
        assert service.get_trading_gate()["decision"] == "ALLOW"
        assert service.can_trade()

    def test_position_degradation_to_recovery_and_back(self):
        service = _start_healthy_service()

        # 1. Position mismatch discovered → DEGRADED
        service.update_component_state(
            "position_service", ComponentState.DEGRADED, StateReasonCode.POSITION_MISMATCH
        )
        assert service.get_state() == {
            "system": "DEGRADED",
            "trading": "TRADING_DEGRADED",
            "operational": "DEGRADED",
        }
        # position degraded does NOT hard-block the gate
        assert service.get_trading_gate()["decision"] == "ALLOW"

        # 2. Recovery starts → operational RECOVERY
        service.update_component_state(
            "position_service",
            ComponentState.RECOVERING,
            StateReasonCode.POSITION_RECOVERY,
        )
        assert service.get_state()["system"] == "DEGRADED"
        assert service.get_state()["operational"] == "RECOVERY"

        # 3. Recovery engine running → system RECOVERING
        service.evaluate(recovery_active=True)
        assert service.get_state()["system"] == "RECOVERING"

        # 4. Recovery completed → back to READY / TRADING_READY / NORMAL
        service.update_component_state(
            "position_service", ComponentState.HEALTHY, StateReasonCode.SYSTEM_HEALTHY
        )
        service.evaluate(recovery_active=False)
        assert service.get_state() == {
            "system": "READY",
            "trading": "TRADING_READY",
            "operational": "NORMAL",
        }

    def test_risk_integrity_chain(self):
        """Position unhealthy → risk integrity untrusted → gate DENY → HALT."""
        service = _start_healthy_service()
        service.update_component_state(
            "position_service", ComponentState.UNHEALTHY, StateReasonCode.POSITION_UNTRUSTED
        )
        # trading degrades first — gate still allows while risk trusts its inputs
        assert service.get_state()["trading"] == "TRADING_DEGRADED"
        assert service.can_trade()

        # risk can no longer trust position → hard halt
        service.set_risk_integrity(RiskIntegrity.UNTRUSTED)
        service.evaluate()
        assert service.get_state()["system"] == "HALTED"
        assert service.get_state()["trading"] == "TRADING_HALTED"
        assert service.get_state()["operational"] == "EMERGENCY"
        assert not service.can_trade()

    def test_critical_component_down_halt_and_restart(self):
        service = _start_healthy_service()

        # Execution engine dies → HALT
        service.update_component_state(
            "execution_engine",
            ComponentState.STOPPED,
            StateReasonCode.EXECUTION_ENGINE_UNHEALTHY,
        )
        assert service.get_state()["system"] == "HALTED"
        assert service.get_state()["trading"] == "TRADING_HALTED"
        assert not service.can_trade()

        # Execution recovers → restart cycle HALTED → STARTING → READY
        service.update_component_state(
            "execution_engine", ComponentState.HEALTHY, StateReasonCode.SYSTEM_HEALTHY
        )
        assert service._system_state is SystemState.STARTING  # auto-restart
        service.complete_startup()
        assert service.get_state() == {
            "system": "READY",
            "trading": "TRADING_READY",
            "operational": "NORMAL",
        }
        assert service.can_trade()

    def test_emergency_and_manual_halt(self):
        service = _start_healthy_service()

        # Emergency halt
        service.emergency_halt()
        assert service.get_state()["operational"] == "EMERGENCY"
        assert service.get_state()["trading"] == "TRADING_HALTED"

        # Clear emergency → system re-enters the restart cycle
        service.clear_emergency()
        assert service._system_state is SystemState.STARTING
        service.complete_startup()
        assert service.get_state()["system"] == "READY"

        # Manual halt keeps the system READY while freezing trading
        service.manual_halt()
        assert service.get_state() == {
            "system": "READY",
            "trading": "TRADING_HALTED",
            "operational": "HALT",
        }
        service.resume()
        assert service.get_state()["trading"] == "TRADING_READY"
        assert service.can_trade()

    def test_heartbeat_timeout_flow(self):
        service = _start_healthy_service()
        service.check_heartbeats(at=NOW + timedelta(seconds=60))
        # event_bus is UNKNOWN → critical path broken → trading halted
        assert service.get_state()["trading"] == "TRADING_HALTED"
        events = service.collect_events()
        assert any(
            e.event_type == "COMPONENT_STATE_CHANGED"
            and e.new_state is ComponentState.UNKNOWN
            and e.reason is StateReasonCode.HEARTBEAT_TIMEOUT
            for e in events
        )


class TestEventTrail:
    def test_event_types_emitted(self):
        service = _start_healthy_service()
        service.update_component_state(
            "position_service", ComponentState.DEGRADED, StateReasonCode.POSITION_MISMATCH
        )
        event_types = {e.event_type for e in service.collect_events()}
        assert {
            "COMPONENT_STATE_CHANGED",
            "SYSTEM_STATE_CHANGED",
            "TRADING_STATE_CHANGED",
        } <= event_types

    def test_event_replay_rebuilds_state(self):
        service = _start_healthy_service()
        service.update_component_state(
            "position_service", ComponentState.DEGRADED, StateReasonCode.POSITION_MISMATCH
        )
        service.update_component_state(
            "position_service", ComponentState.HEALTHY, StateReasonCode.SYSTEM_HEALTHY
        )
        service.collect_events()

        expected = service.get_snapshot()

        # Simulate total loss: fresh repository containing only the event log.
        replay_repository = ControlPlaneRepository()
        for payload in service.repository.get_events():
            replay_repository.append_event(payload)

        rebuilt_service = ControlPlaneService(repository=replay_repository)
        rebuilt = rebuilt_service.rebuild_snapshot()

        assert rebuilt.system_state is expected.system_state
        assert rebuilt.trading_state is expected.trading_state
        assert rebuilt.component_states == expected.component_states

    def test_replayed_events_are_deserializable(self):
        service = _start_healthy_service()
        service.update_component_state(
            "position_service", ComponentState.DEGRADED, StateReasonCode.POSITION_MISMATCH
        )
        service.collect_events()

        payloads = service.repository.get_events()
        by_type = {}
        for payload in payloads:
            by_type.setdefault(payload["event_type"], []).append(payload)

        # boot trail (STARTING→READY) plus the degradation events
        system_events = [
            SystemStateChanged.from_dict(p) for p in by_type["SYSTEM_STATE_CHANGED"]
        ]
        degraded = [e for e in system_events if e.new_state is SystemState.DEGRADED]
        assert len(degraded) == 1
        assert degraded[0].previous_state is SystemState.READY
        assert degraded[0].reason is StateReasonCode.POSITION_MISMATCH

        component_events = [
            ComponentStateChanged.from_dict(p)
            for p in by_type["COMPONENT_STATE_CHANGED"]
        ]
        position_degraded = [
            e
            for e in component_events
            if e.component_id == "position_service"
            and e.new_state is ComponentState.DEGRADED
        ]
        assert len(position_degraded) == 1

        trading_events = [
            TradingStateChanged.from_dict(p)
            for p in by_type["TRADING_STATE_CHANGED"]
        ]
        trading_degraded = [
            e for e in trading_events if e.new_state is TradingState.TRADING_DEGRADED
        ]
        assert len(trading_degraded) == 1
