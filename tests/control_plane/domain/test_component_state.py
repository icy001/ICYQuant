"""Unit tests: ComponentState, ComponentInfo and ComponentRegistry."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.control_plane.domain.component_registry import (
    ComponentCriticality,
    ComponentInfo,
    ComponentRegistry,
    ComponentType,
    default_criticality,
    register_default_components,
)
from services.control_plane.domain.component_state import ComponentState

NOW = datetime.now(timezone.utc)


def _registry_with_healthy_components() -> ComponentRegistry:
    registry = register_default_components()
    for info in registry.list_components():
        info.update_state(ComponentState.HEALTHY, NOW)
        info.mark_heartbeat(NOW)
    return registry


# ============================================================
# ComponentState enum
# ============================================================

class TestComponentState:
    def test_all_states_defined(self):
        expected = {
            "STARTING",
            "HEALTHY",
            "DEGRADED",
            "UNHEALTHY",
            "RECOVERING",
            "STOPPED",
            "UNKNOWN",
        }
        assert {s.value for s in ComponentState} == expected

    def test_health_properties(self):
        assert ComponentState.HEALTHY.is_healthy
        assert not ComponentState.UNHEALTHY.is_healthy

    def test_availability_properties(self):
        assert ComponentState.HEALTHY.is_available
        assert ComponentState.DEGRADED.is_available
        assert ComponentState.RECOVERING.is_available
        assert not ComponentState.UNKNOWN.is_available
        assert not ComponentState.STOPPED.is_available

    def test_degraded_property(self):
        assert ComponentState.UNHEALTHY.is_degraded
        assert ComponentState.UNKNOWN.is_degraded
        assert not ComponentState.RECOVERING.is_degraded


# ============================================================
# ComponentInfo
# ============================================================

class TestComponentInfo:
    def test_defaults(self):
        info = ComponentInfo(
            component_id="event_bus",
            component_type=ComponentType.EVENT_BUS,
            version="1.0.0",
        )
        assert info.state is ComponentState.STARTING
        assert info.criticality is ComponentCriticality.TRADING_CRITICAL
        assert info.health_score == 100.0
        assert info.last_heartbeat_at is None
        assert info.registered_at is not None

    def test_serialization_roundtrip(self):
        info = ComponentInfo(
            component_id="risk_engine",
            component_type=ComponentType.RISK_ENGINE,
            version="2.1.0",
            state=ComponentState.HEALTHY,
            health_score=98.0,
        )
        info.mark_heartbeat(NOW)
        restored = ComponentInfo.from_dict(info.to_dict())
        assert restored == info

    def test_update_state_changed_flag(self):
        info = ComponentInfo(
            component_id="x", component_type=ComponentType.ANALYTICS, version="1.0.0"
        )
        assert info.update_state(ComponentState.HEALTHY, NOW) is True
        assert info.state is ComponentState.HEALTHY
        assert info.update_state(ComponentState.HEALTHY, NOW) is False  # no-op

    def test_health_score_clamped(self):
        info = ComponentInfo(
            component_id="x", component_type=ComponentType.ANALYTICS, version="1.0.0"
        )
        info.set_health_score(150.0)
        assert info.health_score == 100.0
        info.set_health_score(-5.0)
        assert info.health_score == 0.0


class TestDefaultCriticality:
    def test_trading_critical(self):
        for ct in (ComponentType.EVENT_BUS, ComponentType.RISK_ENGINE, ComponentType.EXECUTION_ENGINE):
            assert default_criticality(ct) is ComponentCriticality.TRADING_CRITICAL

    def test_operational(self):
        assert default_criticality(ComponentType.POSITION_SERVICE) is ComponentCriticality.OPERATIONAL
        assert default_criticality(ComponentType.LEDGER_SERVICE) is ComponentCriticality.OPERATIONAL

    def test_non_critical(self):
        assert default_criticality(ComponentType.ANALYTICS) is ComponentCriticality.NON_CRITICAL
        assert default_criticality(ComponentType.DASHBOARD) is ComponentCriticality.NON_CRITICAL


# ============================================================
# ComponentRegistry
# ============================================================

class TestComponentRegistry:
    def test_registration(self):
        registry = ComponentRegistry()
        info = registry.register(
            component_id="event_bus",
            component_type=ComponentType.EVENT_BUS,
            version="1.0.0",
        )
        assert registry.has("event_bus")
        assert registry.get("event_bus") is info
        assert registry.component_count() == 1

    def test_register_is_idempotent(self):
        registry = ComponentRegistry()
        first = registry.register("x", ComponentType.ANALYTICS, "1.0.0")
        second = registry.register("x", ComponentType.ANALYTICS, "9.9.9")
        assert first is second
        assert registry.component_count() == 1

    def test_update_state(self):
        registry = _registry_with_healthy_components()
        previous, changed = registry.update_state(
            "position_service", ComponentState.DEGRADED, NOW
        )
        assert previous is ComponentState.HEALTHY
        assert changed is True
        assert registry.get("position_service").state is ComponentState.DEGRADED

    def test_update_state_unknown_component(self):
        registry = ComponentRegistry()
        assert registry.update_state("missing", ComponentState.HEALTHY, NOW) is None

    def test_heartbeat_updates_timestamp(self):
        registry = _registry_with_healthy_components()
        info = registry.heartbeat("event_bus", NOW + timedelta(seconds=10))
        assert info.last_heartbeat_at == NOW + timedelta(seconds=10)

    def test_heartbeat_timeout_marks_unknown(self):
        registry = _registry_with_healthy_components()
        # No heartbeat for 20s with a 15s timeout → UNKNOWN.
        timed_out = registry.apply_heartbeat_timeout(
            NOW + timedelta(seconds=20), timeout_ms=15000
        )
        assert len(timed_out) == registry.component_count()
        for component_id, previous in timed_out:
            assert previous is ComponentState.HEALTHY
            assert registry.get(component_id).state is ComponentState.UNKNOWN

    def test_heartbeat_timeout_within_window(self):
        registry = _registry_with_healthy_components()
        timed_out = registry.apply_heartbeat_timeout(
            NOW + timedelta(seconds=10), timeout_ms=15000
        )
        assert timed_out == []

    def test_heartbeat_timeout_skips_never_heartbeated(self):
        registry = register_default_components()  # never heartbeated
        timed_out = registry.apply_heartbeat_timeout(
            NOW + timedelta(seconds=60), timeout_ms=15000
        )
        assert timed_out == []

    def test_states_map(self):
        registry = _registry_with_healthy_components()
        states = registry.states()
        assert states["event_bus"] is ComponentState.HEALTHY
        assert set(states.keys()) == {ct.value for ct in ComponentType if ct.value in states}

    def test_register_default_components(self):
        registry = register_default_components(version="1.0.0")
        assert registry.component_count() == 9
        event_bus = registry.get("event_bus")
        assert event_bus.criticality is ComponentCriticality.TRADING_CRITICAL
        assert registry.get("position_service").criticality is ComponentCriticality.OPERATIONAL

    def test_critical_components_query(self):
        registry = _registry_with_healthy_components()
        critical_ids = {c.component_id for c in registry.critical_components()}
        assert critical_ids == {"event_bus", "risk_engine", "execution_engine"}
