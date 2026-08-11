"""
Tests for EventEnvelope — serialization, deserialization,
metadata propagation, and delivery tracking.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.integration.event_envelope import (
    ConsistencyState,
    DeliveryRecord,
    DeliveryState,
    EventEnvelope,
)


class TestEventEnvelope:
    """Core envelope construction and serialization tests."""

    def test_default_construction(self) -> None:
        """An envelope created with defaults has sensible values."""
        env = EventEnvelope()
        assert env.event_id.startswith("EVT-")
        assert env.event_version == 1
        assert env.aggregate_version == 1
        assert isinstance(env.occurred_at, datetime)
        assert env.payload == {}
        assert env.metadata == {}

    def test_from_event_factory(self) -> None:
        """The from_event classmethod builds a complete envelope."""
        env = EventEnvelope.from_event(
            event_id="EVT-EXEC-000001",
            event_type="ORDER_FILLED",
            event_version=1,
            aggregate_type="ORDER",
            aggregate_id="ORD-001",
            aggregate_version=5,
            producer="OMS",
            payload={"order_id": "ORD-001", "filled_quantity": 1000},
            correlation_id="CORR-001",
            causation_id="EVT-EXEC-000000",
            lineage_id="LIN-001",
            metadata={"trace_id": "abc123"},
        )

        assert env.event_id == "EVT-EXEC-000001"
        assert env.event_type == "ORDER_FILLED"
        assert env.event_version == 1
        assert env.aggregate_type == "ORDER"
        assert env.aggregate_id == "ORD-001"
        assert env.aggregate_version == 5
        assert env.producer == "OMS"
        assert env.correlation_id == "CORR-001"
        assert env.causation_id == "EVT-EXEC-000000"
        assert env.lineage_id == "LIN-001"
        assert env.payload["filled_quantity"] == 1000
        assert env.metadata["trace_id"] == "abc123"

    def test_to_dict_and_from_dict_roundtrip(self) -> None:
        """Serializing to dict and back preserves all fields."""
        original = EventEnvelope.from_event(
            event_id="EVT-001",
            event_type="ORDER_CREATED",
            event_version=1,
            aggregate_type="ORDER",
            aggregate_id="ORD-100",
            aggregate_version=1,
            producer="OMS",
            payload={"symbol": "NVDA", "side": "BUY", "quantity": 500},
            correlation_id="CORR-A",
            causation_id="EVT-SIG-001",
            lineage_id="LIN-A",
        )

        data = original.to_dict()
        restored = EventEnvelope.from_dict(data)

        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type
        assert restored.event_version == original.event_version
        assert restored.aggregate_type == original.aggregate_type
        assert restored.aggregate_id == original.aggregate_id
        assert restored.aggregate_version == original.aggregate_version
        assert restored.producer == original.producer
        assert restored.correlation_id == original.correlation_id
        assert restored.causation_id == original.causation_id
        assert restored.lineage_id == original.lineage_id
        assert restored.payload == dict(original.payload)
        assert restored.metadata == dict(original.metadata)

    def test_correlation_id_propagation(self) -> None:
        """Correlation ID is carried across all events in a chain."""
        corr_id = "STRATEGY-20260811-00001"
        env1 = EventEnvelope.from_event(
            event_id="EVT-001", event_type="SIGNAL", event_version=1,
            aggregate_type="STRATEGY", aggregate_id="SIG-1", aggregate_version=1,
            producer="Strategy", payload={}, correlation_id=corr_id,
        )
        env2 = EventEnvelope.from_event(
            event_id="EVT-002", event_type="ORDER_CREATED", event_version=1,
            aggregate_type="ORDER", aggregate_id="ORD-1", aggregate_version=1,
            producer="OMS", payload={}, correlation_id=corr_id,
        )
        env3 = EventEnvelope.from_event(
            event_id="EVT-003", event_type="ORDER_FILLED", event_version=1,
            aggregate_type="ORDER", aggregate_id="ORD-1", aggregate_version=2,
            producer="OMS", payload={}, correlation_id=corr_id,
        )
        assert env1.correlation_id == env2.correlation_id == env3.correlation_id == corr_id

    def test_causation_chain(self) -> None:
        """Causation IDs form a chain: A → B → C → D."""
        a = EventEnvelope.from_event(
            event_id="A", event_type="SIGNAL", event_version=1,
            aggregate_type="STRATEGY", aggregate_id="S-1", aggregate_version=1,
            producer="Strategy", payload={},
        )
        b = EventEnvelope.from_event(
            event_id="B", event_type="ORDER_CREATED", event_version=1,
            aggregate_type="ORDER", aggregate_id="O-1", aggregate_version=1,
            producer="OMS", payload={}, causation_id="A",
        )
        c = EventEnvelope.from_event(
            event_id="C", event_type="ORDER_FILLED", event_version=1,
            aggregate_type="ORDER", aggregate_id="O-1", aggregate_version=2,
            producer="OMS", payload={}, causation_id="B",
        )
        assert b.causation_id == "A"
        assert c.causation_id == "B"

    def test_lineage_id_shared(self) -> None:
        """All events in the same trading lineage share the same lineage_id."""
        lineage = "LIN-20260811-000001"
        for i in range(5):
            env = EventEnvelope.from_event(
                event_id=f"EVT-{i}", event_type="ORDER_FILLED", event_version=1,
                aggregate_type="ORDER", aggregate_id=f"ORD-{i}", aggregate_version=1,
                producer="OMS", payload={}, lineage_id=lineage,
            )
            assert env.lineage_id == lineage

    def test_event_id_uniqueness(self) -> None:
        """Each envelope gets a unique event_id by default."""
        ids = {EventEnvelope().event_id for _ in range(100)}
        assert len(ids) == 100  # All unique

    def test_frozen_immutable(self) -> None:
        """Envelope is frozen — cannot be mutated after creation."""
        env = EventEnvelope()
        with pytest.raises(Exception):
            env.event_id = "NEW-ID"  # type: ignore[misc]

    def test_occurred_at_is_utc(self) -> None:
        """occurred_at must be timezone-aware UTC."""
        env = EventEnvelope()
        assert env.occurred_at.tzinfo is not None
        assert env.occurred_at.utcoffset() is not None


class TestDeliveryRecord:
    """Tests for per-consumer delivery tracking."""

    def test_default_state_is_pending(self) -> None:
        env = EventEnvelope()
        record = env.with_delivery_state(DeliveryState.PENDING, "position-service")
        assert record.state == DeliveryState.PENDING
        assert record.consumer_group == "position-service"
        assert record.attempt == 0

    def test_delivery_state_transitions(self) -> None:
        env = EventEnvelope()
        states = [
            DeliveryState.PENDING,
            DeliveryState.DELIVERED,
            DeliveryState.RETRYING,
            DeliveryState.FAILED,
            DeliveryState.DEAD_LETTER,
        ]
        for state in states:
            record = env.with_delivery_state(state, "test-group")
            assert record.state == state


class TestConsistencyState:
    """Tests for cross-domain consistency tracking."""

    def test_consistency_state_values(self) -> None:
        assert ConsistencyState.SYNCED == "SYNCED"
        assert ConsistencyState.LAGGING == "LAGGING"
        assert ConsistencyState.RECOVERING == "RECOVERING"
        assert ConsistencyState.MISMATCHED == "MISMATCHED"

    def test_default_state(self) -> None:
        # Default should be SYNCED (check via consumer)
        from services.integration.event_consumer import EventConsumer
        from services.integration.event_registry import EventRegistry

        registry = EventRegistry()

        class DummyConsumer(EventConsumer):
            SUBSCRIBED_EVENTS = frozenset({"TEST"})

            def handle(self, envelope: EventEnvelope) -> None:
                pass

        consumer = DummyConsumer(registry, "test")
        assert consumer.get_consistency_state("unknown-agg") == ConsistencyState.SYNCED
