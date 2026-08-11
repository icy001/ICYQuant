"""
Tests for EventRouter — routing events to consumer groups,
fan-out, and dynamic registration.
"""

from __future__ import annotations

import pytest

from services.integration.event_registry import EventRegistry
from services.integration.event_router import EventRouter


@pytest.fixture
def registry() -> EventRegistry:
    reg = EventRegistry()
    reg.register_defaults()
    return reg


@pytest.fixture
def router(registry: EventRegistry) -> EventRouter:
    r = EventRouter(registry)
    r.sync_from_registry()
    return r


class TestEventRouter:
    """Core routing tests."""

    def test_route_order_filled(self, router: EventRouter) -> None:
        """ORDER_FILLED fans out to position, ledger, risk, audit."""
        groups = router.route("ORDER_FILLED")
        assert "position-service" in groups
        assert "ledger-service" in groups
        assert "risk-service" in groups
        assert "audit-service" in groups

    def test_route_order_rejected(self, router: EventRouter) -> None:
        """ORDER_REJECTED only goes to risk and audit."""
        groups = router.route("ORDER_REJECTED")
        assert "risk-service" in groups
        assert "audit-service" in groups
        assert "position-service" not in groups
        assert "ledger-service" not in groups

    def test_has_consumers(self, router: EventRouter) -> None:
        assert router.has_consumers("ORDER_FILLED")
        assert not router.has_consumers("NONEXISTENT_EVENT")

    def test_register_consumer(self, router: EventRouter) -> None:
        """Dynamically register a new consumer for an event."""
        router.register_consumer("ORDER_FILLED", "analytics-service")
        groups = router.route("ORDER_FILLED")
        assert "analytics-service" in groups

    def test_register_consumer_unknown_event_raises(self, router: EventRouter) -> None:
        with pytest.raises(KeyError, match="unknown event"):
            router.register_consumer("NONEXISTENT", "some-service")

    def test_unregister_consumer(self, router: EventRouter) -> None:
        """Unregister a consumer."""
        router.register_consumer("ORDER_FILLED", "analytics-service")
        assert "analytics-service" in router.route("ORDER_FILLED")

        router.unregister_consumer("ORDER_FILLED", "analytics-service")
        assert "analytics-service" not in router.route("ORDER_FILLED")

    def test_unregister_nonexistent_no_error(self, router: EventRouter) -> None:
        """Unregistering a non-existent consumer is a no-op."""
        router.unregister_consumer("ORDER_FILLED", "nonexistent-service")
        # Should not raise

    def test_sync_from_registry(self, router: EventRouter) -> None:
        """After sync, routing matches registry contracts."""
        groups = router.route("ORDER_CREATED")
        assert "position-service" in groups

    def test_fan_out_single_event_multiple_consumers(self, router: EventRouter) -> None:
        """One event → multiple consumers (fan-out)."""
        groups = router.route("ORDER_FILLED")
        # At minimum: position, ledger, risk, audit
        assert len(groups) >= 4

    def test_route_returns_frozenset(self, router: EventRouter) -> None:
        """route() returns an immutable frozenset."""
        groups = router.route("ORDER_FILLED")
        assert isinstance(groups, frozenset)

    def test_list_consumers(self, router: EventRouter) -> None:
        """list_consumers() returns a mapping of event types to consumers."""
        mapping = router.list_consumers()
        assert "ORDER_FILLED" in mapping
        assert "ORDER_CREATED" in mapping
        assert "position-service" in mapping["ORDER_FILLED"]
        assert "ledger-service" in mapping["ORDER_FILLED"]

    def test_router_independent_of_registry_mutations(self, router: EventRouter) -> None:
        """
        Dynamic registrations in the router do NOT affect the source registry.
        The router maintains its own routing table.
        """
        router.register_consumer("ORDER_FILLED", "custom-service")
        # Router has it
        assert "custom-service" in router.route("ORDER_FILLED")
        # Registry does NOT
        assert "custom-service" not in router._registry.consumers_for("ORDER_FILLED")

    def test_empty_router(self, registry: EventRegistry) -> None:
        """Router without sync returns empty for unknown events."""
        router = EventRouter(registry)
        groups = router.route("ORDER_FILLED")
        # Falls back to registry consumers
        assert "position-service" in groups
