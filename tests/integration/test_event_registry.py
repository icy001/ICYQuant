"""
Tests for EventRegistry — registration, lookup, deserialization,
and integration with EventContract.
"""

from __future__ import annotations

import pytest

from services.integration.event_contract import (
    EventContract,
    EVENT_CONTRACT_ORDER_FILLED,
    EVENT_CONTRACT_ORDER_CREATED,
    EVENT_CONTRACT_POSITION_INCREASED,
    EVENT_CONTRACT_LEDGER_ENTRY_CREATED,
)
from services.integration.event_registry import EventRegistry, RegistryEntry


class TestEventRegistry:
    """Core registry tests."""

    def test_empty_registry(self) -> None:
        registry = EventRegistry()
        assert len(registry) == 0
        assert registry.list_event_types() == []

    def test_register_single_contract(self) -> None:
        registry = EventRegistry()
        registry.register(EVENT_CONTRACT_ORDER_FILLED)
        assert len(registry) == 1
        assert ("ORDER_FILLED", 1) in registry

    def test_register_defaults(self) -> None:
        registry = EventRegistry()
        registry.register_defaults()
        # We expect all canonical contracts to be registered
        assert len(registry) > 10
        assert ("ORDER_FILLED", 1) in registry
        assert ("ORDER_CREATED", 1) in registry
        assert ("POSITION_INCREASED", 1) in registry
        assert ("LEDGER_ENTRY_CREATED", 1) in registry

    def test_get_contract(self) -> None:
        registry = EventRegistry()
        registry.register(EVENT_CONTRACT_ORDER_FILLED)

        contract = registry.get_contract("ORDER_FILLED")
        assert contract.event_type == "ORDER_FILLED"
        assert contract.producer == "OMS"
        assert contract.version == 1
        assert "filled_quantity" in contract.required_fields
        assert "position-service" in contract.consumers
        assert "ledger-service" in contract.consumers

    def test_get_contract_missing_raises(self) -> None:
        registry = EventRegistry()
        with pytest.raises(KeyError, match="UNKNOWN"):
            registry.get_contract("UNKNOWN_EVENT")

    def test_consumers_for(self) -> None:
        registry = EventRegistry()
        registry.register(EVENT_CONTRACT_ORDER_FILLED)

        consumers = registry.consumers_for("ORDER_FILLED")
        assert "position-service" in consumers
        assert "ledger-service" in consumers
        assert "risk-service" in consumers
        assert "audit-service" in consumers

    def test_consumers_for_missing_raises(self) -> None:
        registry = EventRegistry()
        with pytest.raises(KeyError):
            registry.consumers_for("NONEXISTENT")

    def test_has_event(self) -> None:
        registry = EventRegistry()
        registry.register(EVENT_CONTRACT_ORDER_CREATED)
        assert registry.has_event("ORDER_CREATED")
        assert not registry.has_event("NONEXISTENT")
        assert registry.has_event("ORDER_CREATED", version=1)
        assert not registry.has_event("ORDER_CREATED", version=2)

    def test_deserializer_registration(self) -> None:
        registry = EventRegistry()

        def my_deserializer(payload: dict) -> dict:
            return {**payload, "deserialized": True}

        registry.register(EVENT_CONTRACT_ORDER_FILLED, deserializer=my_deserializer)

        result = registry.deserialize("ORDER_FILLED", 1, {"qty": 100})
        assert result["deserialized"] is True
        assert result["qty"] == 100

    def test_deserialize_without_deserializer_falls_back_to_dict(self) -> None:
        registry = EventRegistry()
        registry.register(EVENT_CONTRACT_ORDER_FILLED)

        payload = {"order_id": "ORD-1", "filled_quantity": 500, "average_price": 180.0}
        result = registry.deserialize("ORDER_FILLED", 1, payload)
        assert isinstance(result, dict)
        assert result["order_id"] == "ORD-1"

    def test_list_event_types(self) -> None:
        registry = EventRegistry()
        registry.register(EVENT_CONTRACT_ORDER_FILLED)
        registry.register(EVENT_CONTRACT_POSITION_INCREASED)

        types = registry.list_event_types()
        assert "ORDER_FILLED" in types
        assert "POSITION_INCREASED" in types
        assert types == sorted(types)  # Always sorted

    def test_list_all(self) -> None:
        registry = EventRegistry()
        registry.register(EVENT_CONTRACT_ORDER_FILLED)
        registry.register(EVENT_CONTRACT_POSITION_INCREASED)

        all_entries = registry.list_all()
        assert len(all_entries) == 2

        # Each entry is (event_type, version, producer, consumers)
        types = {e[0] for e in all_entries}
        assert "ORDER_FILLED" in types
        assert "POSITION_INCREASED" in types

    def test_version_isolation(self) -> None:
        """v1 and v2 of the same event coexist independently."""
        registry = EventRegistry()

        contract_v1 = EventContract(
            event_type="ORDER_FILLED",
            version=1,
            producer="OMS",
            required_fields=frozenset({"filled_quantity", "average_price"}),
            consumers=frozenset({"position-service-v1"}),
        )
        contract_v2 = EventContract(
            event_type="ORDER_FILLED",
            version=2,
            producer="OMS",
            required_fields=frozenset({"filled_quantity", "average_price", "venue", "liquidity_flag"}),
            consumers=frozenset({"position-service-v2"}),
        )

        registry.register(contract_v1)
        registry.register(contract_v2)

        assert registry.get_contract("ORDER_FILLED", version=1) == contract_v1
        assert registry.get_contract("ORDER_FILLED", version=2) == contract_v2

        assert registry.consumers_for("ORDER_FILLED", version=1) == frozenset({"position-service-v1"})
        assert registry.consumers_for("ORDER_FILLED", version=2) == frozenset({"position-service-v2"})


class TestEventContract:
    """Validation and schema tests for EventContract."""

    def test_validate_success(self) -> None:
        payload = {
            "order_id": "ORD-1",
            "filled_quantity": 1000,
            "average_price": 180.0,
            "cumulative_quantity": 1000,
        }
        EVENT_CONTRACT_ORDER_FILLED.validate_payload(payload)  # Should not raise

    def test_validate_missing_required_raises(self) -> None:
        payload = {"order_id": "ORD-1"}  # Missing filled_quantity, average_price, cumulative_quantity
        with pytest.raises(ValueError, match="missing required fields"):
            EVENT_CONTRACT_ORDER_FILLED.validate_payload(payload)

    def test_validate_optional_fields_ok(self) -> None:
        payload = {
            "order_id": "ORD-1",
            "filled_quantity": 500,
            "average_price": 180.0,
            "cumulative_quantity": 500,
            "execution_id": "EXEC-1",  # Optional
            "venue": "NASDAQ",  # Optional
            "liquidity_flag": "TAKER",  # Optional
        }
        EVENT_CONTRACT_ORDER_FILLED.validate_payload(payload)  # Should not raise

    def test_rejected_event_consumers(self) -> None:
        """ORDER_REJECTED goes to risk and audit only."""
        from services.integration.event_contract import EVENT_CONTRACT_ORDER_REJECTED

        consumers = EVENT_CONTRACT_ORDER_REJECTED.consumers
        assert "risk-service" in consumers
        assert "audit-service" in consumers
        assert "position-service" not in consumers  # Position doesn't care about rejects
        assert "ledger-service" not in consumers  # Ledger doesn't care about rejects

    def test_all_contracts_have_producer(self) -> None:
        """Every contract must declare who owns the event."""
        from services.integration.event_contract import ALL_CONTRACTS
        for contract in ALL_CONTRACTS:
            assert contract.producer, f"{contract.event_type} has no producer"

    def test_all_contracts_have_event_type(self) -> None:
        """Every contract must have a non-empty event_type."""
        from services.integration.event_contract import ALL_CONTRACTS
        for contract in ALL_CONTRACTS:
            assert contract.event_type, "Contract has empty event_type"
