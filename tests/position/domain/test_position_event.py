"""
Tests for Position domain events.
"""

from __future__ import annotations

import pytest

from services.position.domain.position_event import (
    PositionClosedEvent,
    PositionDecreasedEvent,
    PositionEvent,
    PositionEventType,
    PositionIncreasedEvent,
    PositionRebuiltEvent,
)


class TestPositionIncreasedEvent:
    """POSITION_INCREASED event construction and serialization."""

    def test_create_event(self) -> None:
        event = PositionIncreasedEvent(
            position_id="POS-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            side="LONG",
            previous_quantity=0,
            delta_quantity=500,
            new_quantity=500,
            average_price=180.0,
            source_order_id="ORD-001",
            source_execution_id="EXEC-001",
            source_event_id="EVT-001",
        )
        assert event.event_type == PositionEventType.POSITION_INCREASED
        assert event.position_id == "POS-001"
        assert event.new_quantity == 500
        assert event.delta_quantity == 500

    def test_to_dict_and_from_dict_roundtrip(self) -> None:
        event = PositionIncreasedEvent(
            position_id="POS-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            side="LONG",
            previous_quantity=100,
            delta_quantity=200,
            new_quantity=300,
            average_price=181.0,
            source_order_id="ORD-001",
            source_execution_id="EXEC-001",
            source_event_id="EVT-001",
            correlation_id="CORR-001",
            causation_id="CAUS-001",
            lineage_id="LIN-001",
        )
        d = event.to_dict()
        restored = PositionEvent.from_dict(d)
        assert isinstance(restored, PositionIncreasedEvent)
        assert restored.position_id == "POS-001"
        assert restored.delta_quantity == 200
        assert restored.correlation_id == "CORR-001"
        assert restored.causation_id == "CAUS-001"
        assert restored.lineage_id == "LIN-001"

    def test_lineage_preserved_in_serialization(self) -> None:
        event = PositionIncreasedEvent(
            position_id="P1",
            account_id="A1",
            instrument_id="NVDA",
            side="LONG",
            previous_quantity=0,
            delta_quantity=100,
            new_quantity=100,
            average_price=180,
            source_order_id="ORD-001",
            source_execution_id="EXEC-001",
            source_event_id="EVT-001",
            correlation_id="CORR-001",
            causation_id="CAUS-001",
            lineage_id="LIN-001",
        )
        d = event.to_dict()
        assert d["correlation_id"] == "CORR-001"
        assert d["source_order_id"] == "ORD-001"
        assert d["source_event_id"] == "EVT-001"


class TestPositionDecreasedEvent:
    """POSITION_DECREASED event."""

    def test_create_event(self) -> None:
        event = PositionDecreasedEvent(
            position_id="POS-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            side="LONG",
            previous_quantity=1000,
            delta_quantity=-300,
            new_quantity=700,
            average_price=180.0,
            realized_pnl=1500.0,
            source_order_id="ORD-002",
            source_execution_id="EXEC-002",
            source_event_id="EVT-002",
        )
        assert event.event_type == PositionEventType.POSITION_DECREASED
        assert event.delta_quantity == -300
        assert event.new_quantity == 700
        assert event.realized_pnl == 1500.0

    def test_roundtrip(self) -> None:
        event = PositionDecreasedEvent(
            position_id="P1",
            account_id="A1",
            instrument_id="AAPL",
            side="LONG",
            previous_quantity=500,
            delta_quantity=-200,
            new_quantity=300,
            average_price=150.0,
            realized_pnl=1000.0,
            source_order_id="ORD-001",
            source_execution_id="EXEC-001",
            source_event_id="EVT-001",
        )
        d = event.to_dict()
        restored = PositionEvent.from_dict(d)
        assert isinstance(restored, PositionDecreasedEvent)
        assert restored.realized_pnl == 1000.0


class TestPositionClosedEvent:
    """POSITION_CLOSED event."""

    def test_create_event(self) -> None:
        event = PositionClosedEvent(
            position_id="POS-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            side="LONG",
            previous_quantity=1000,
            delta_quantity=-1000,
            new_quantity=0,
            average_price=0.0,
            realized_pnl=5000.0,
            source_order_id="ORD-003",
            source_execution_id="EXEC-003",
            source_event_id="EVT-003",
        )
        assert event.event_type == PositionEventType.POSITION_CLOSED
        assert event.new_quantity == 0

    def test_roundtrip(self) -> None:
        event = PositionClosedEvent(
            position_id="P1",
            account_id="A1",
            instrument_id="TSLA",
            side="LONG",
            previous_quantity=200,
            delta_quantity=-200,
            new_quantity=0,
            average_price=0.0,
            realized_pnl=10000.0,
            source_order_id="ORD-001",
            source_execution_id="EXEC-001",
            source_event_id="EVT-001",
        )
        d = event.to_dict()
        restored = PositionEvent.from_dict(d)
        assert isinstance(restored, PositionClosedEvent)
        assert restored.realized_pnl == 10000.0


class TestPositionRebuiltEvent:
    """POSITION_REBUILT event (from replay/recovery)."""

    def test_create_event(self) -> None:
        event = PositionRebuiltEvent(
            position_id="POS-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            side="LONG",
            previous_quantity=0,
            delta_quantity=500,
            new_quantity=500,
            average_price=180.0,
            source_event_id="EVT-RECOVERY-001",
        )
        assert event.event_type == PositionEventType.POSITION_REBUILT

    def test_roundtrip(self) -> None:
        event = PositionRebuiltEvent(
            position_id="P1",
            account_id="A1",
            instrument_id="NVDA",
            side="LONG",
            previous_quantity=0,
            delta_quantity=300,
            new_quantity=300,
            average_price=180,
            source_event_id="EVT-RECOVERY-001",
        )
        d = event.to_dict()
        restored = PositionEvent.from_dict(d)
        assert isinstance(restored, PositionRebuiltEvent)


class TestEventTypeRegistry:
    """Event type constants."""

    def test_all_types_defined(self) -> None:
        assert PositionEventType.POSITION_INCREASED == "POSITION_INCREASED"
        assert PositionEventType.POSITION_DECREASED == "POSITION_DECREASED"
        assert PositionEventType.POSITION_CLOSED == "POSITION_CLOSED"
        assert PositionEventType.POSITION_REBUILT == "POSITION_REBUILT"


class TestDeserializeUnknownType:
    """Fallback for unknown event types."""

    def test_fallback_to_base(self) -> None:
        d = {
            "event_type": "UNKNOWN_TYPE",
            "position_id": "P1",
            "account_id": "A1",
            "instrument_id": "NVDA",
            "side": "LONG",
            "previous_quantity": 0,
            "delta_quantity": 100,
            "new_quantity": 100,
            "average_price": 180,
        }
        event = PositionEvent.from_dict(d)
        assert isinstance(event, PositionEvent)
        assert event.event_type == "UNKNOWN_TYPE"
