"""
Tests for Position aggregate — the core domain logic.
"""

from __future__ import annotations

import pytest

from services.position.domain.position import (
    Position,
    PositionOverFillError,
    PositionSide,
    PositionStatus,
)


class TestPositionCreation:
    """Position factory and initial state."""

    def test_open_long_creates_zero_position(self) -> None:
        pos = Position.open_long(
            position_id="POS-001",
            account_id="ACC-001",
            instrument_id="NVDA",
        )
        assert pos.position_id == "POS-001"
        assert pos.account_id == "ACC-001"
        assert pos.instrument_id == "NVDA"
        assert pos.side == PositionSide.LONG
        assert pos.quantity == 0.0
        assert pos.average_price == 0.0
        assert pos.version == 1
        assert pos.status == PositionStatus.OPEN

    def test_open_long_with_initial_quantity(self) -> None:
        pos = Position.open_long(
            position_id="POS-001",
            account_id="ACC-001",
            instrument_id="NVDA",
            quantity=500.0,
            average_price=180.0,
        )
        assert pos.quantity == 500.0
        assert pos.average_price == 180.0

    def test_open_short(self) -> None:
        pos = Position.open_short(
            position_id="POS-002",
            account_id="ACC-001",
            instrument_id="NVDA",
        )
        assert pos.side == PositionSide.SHORT
        assert pos.quantity == 0.0

    def test_key_identity(self) -> None:
        pos = Position.open_long("POS-001", "ACC-001", "NVDA")
        assert pos.key == ("ACC-001", "NVDA", PositionSide.LONG)


class TestPositionProperties:
    """Position computed properties."""

    def test_exposure(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA", quantity=100, average_price=180)
        assert pos.exposure == 18000.0

    def test_is_open(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA", quantity=100, average_price=180)
        assert pos.is_open is True
        assert pos.is_closed is False

    def test_is_closed_when_zero(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA")
        assert pos.is_closed is True

    def test_signed_quantity_long(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA", quantity=100, average_price=180)
        assert pos.signed_quantity == 100.0

    def test_signed_quantity_short(self) -> None:
        pos = Position.open_short("P1", "A1", "NVDA", quantity=100, average_price=180)
        assert pos.signed_quantity == -100.0


class TestApplyFill:
    """BUY fill application to LONG position."""

    def test_apply_first_fill(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA")
        event = pos.apply_fill(
            fill_quantity=500,
            fill_price=180,
            execution_id="EXEC-001",
            order_id="ORD-001",
            source_event_id="EVT-001",
        )
        assert pos.quantity == 500
        assert pos.average_price == 180
        assert pos.version == 2
        assert event is not None
        assert event.event_type == "POSITION_INCREASED"
        assert event.new_quantity == 500
        assert event.delta_quantity == 500
        assert event.source_order_id == "ORD-001"
        assert event.source_execution_id == "EXEC-001"

    def test_apply_second_fill_weighted_avg(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA", quantity=500, average_price=180)
        event = pos.apply_fill(
            fill_quantity=500,
            fill_price=182,
            execution_id="EXEC-002",
            order_id="ORD-002",
            source_event_id="EVT-002",
        )
        assert pos.quantity == 1000
        assert pos.average_price == pytest.approx(181.0)
        assert event is not None
        assert event.new_quantity == 1000
        assert event.delta_quantity == 500

    def test_apply_fill_preserves_lineage(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA")
        pos.apply_fill(
            fill_quantity=100,
            fill_price=180,
            execution_id="EXEC-001",
            order_id="ORD-001",
            source_event_id="EVT-001",
            correlation_id="CORR-001",
            causation_id="CAUS-001",
            lineage_id="LIN-001",
        )
        event = pos.collect_events()[0]
        assert event.correlation_id == "CORR-001"
        assert event.causation_id == "CAUS-001"
        assert event.lineage_id == "LIN-001"

    def test_apply_fill_returns_none_for_zero_quantity(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA")
        event = pos.apply_fill(
            fill_quantity=0,
            fill_price=180,
            execution_id="EXEC-001",
            order_id="ORD-001",
            source_event_id="EVT-001",
        )
        assert event is None
        assert pos.quantity == 0

    def test_apply_fill_raises_for_negative_price(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA")
        with pytest.raises(ValueError, match="fill_price"):
            pos.apply_fill(
                fill_quantity=100,
                fill_price=-10,
                execution_id="EXEC-001",
                order_id="ORD-001",
                source_event_id="EVT-001",
            )

    def test_apply_fill_builds_position_from_zero(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA")
        pos.apply_fill(
            fill_quantity=200,
            fill_price=180,
            execution_id="EXEC-001",
            order_id="ORD-001",
            source_event_id="EVT-001",
        )
        pos.apply_fill(
            fill_quantity=300,
            fill_price=182,
            execution_id="EXEC-002",
            order_id="ORD-001",
            source_event_id="EVT-002",
        )
        assert pos.quantity == 500
        assert pos.average_price == pytest.approx(181.2)


class TestApplyReduction:
    """SELL reduction on LONG position."""

    def test_reduce_position(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA", quantity=1000, average_price=180)
        event = pos.apply_reduction(
            reduction_quantity=300,
            fill_price=185,
            execution_id="EXEC-003",
            order_id="ORD-003",
            source_event_id="EVT-003",
        )
        assert pos.quantity == 700
        assert event is not None
        assert event.event_type == "POSITION_DECREASED"
        assert event.new_quantity == 700
        assert event.delta_quantity == -300
        assert event.realized_pnl == pytest.approx(1500.0)  # 300 * (185 - 180)

    def test_close_position(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA", quantity=1000, average_price=180)
        event = pos.apply_reduction(
            reduction_quantity=1000,
            fill_price=185,
            execution_id="EXEC-004",
            order_id="ORD-004",
            source_event_id="EVT-004",
        )
        assert pos.quantity == 0
        assert pos.status == PositionStatus.CLOSED
        assert event is not None
        assert event.event_type == "POSITION_CLOSED"
        assert event.new_quantity == 0

    def test_reduction_returns_none_for_zero(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA", quantity=100, average_price=180)
        event = pos.apply_reduction(
            reduction_quantity=0,
            fill_price=185,
            execution_id="EXEC-001",
            order_id="ORD-001",
            source_event_id="EVT-001",
        )
        assert event is None

    def test_reduction_over_fill_raises(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA", quantity=100, average_price=180)
        with pytest.raises(PositionOverFillError):
            pos.apply_reduction(
                reduction_quantity=200,
                fill_price=185,
                execution_id="EXEC-001",
                order_id="ORD-001",
                source_event_id="EVT-001",
            )


class TestReversalDetection:
    """Reversal detection — catching position flips."""

    def test_no_reversal_when_reduction_is_less_than_position(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA", quantity=500, average_price=180)
        assert pos.detect_reversal(reduction_quantity=300, order_id="ORD-001") is False

    def test_no_reversal_when_reduction_equals_position(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA", quantity=500, average_price=180)
        # Equal is a full close, not a reversal
        assert pos.detect_reversal(reduction_quantity=500, order_id="ORD-001") is False

    def test_reversal_detected(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA", quantity=500, average_price=180)
        assert pos.detect_reversal(reduction_quantity=800, order_id="ORD-001") is True


class TestSnapshot:
    """Position snapshot and state projection."""

    def test_snapshot_captures_state(self) -> None:
        pos = Position.open_long(
            "P1", "A1", "NVDA", quantity=1000, average_price=180
        )
        pos.apply_fill(
            fill_quantity=500,
            fill_price=182,
            execution_id="EXEC-001",
            order_id="ORD-001",
            source_event_id="EVT-001",
        )
        snap = pos.snapshot()
        assert snap.quantity == 1500
        assert snap.average_price == pytest.approx(180.66666666666666)
        assert snap.version == 2
        assert snap.position_id == "P1"
        assert snap.last_execution_id == "EXEC-001"

    def test_snapshot_to_dict(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA", quantity=100, average_price=180)
        d = pos.snapshot().to_dict()
        assert d["position_id"] == "P1"
        assert d["account_id"] == "A1"
        assert d["instrument_id"] == "NVDA"
        assert d["quantity"] == 100


class TestEventCollection:
    """Collecting pending domain events."""

    def test_collect_events_drains(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA")
        pos.apply_fill(
            fill_quantity=100,
            fill_price=180,
            execution_id="EXEC-001",
            order_id="ORD-001",
            source_event_id="EVT-001",
        )
        events = pos.collect_events()
        assert len(events) == 1
        assert events[0].event_type == "POSITION_INCREASED"

        # Second collect should be empty (drained)
        events2 = pos.collect_events()
        assert len(events2) == 0

    def test_multiple_events_accumulated(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA")
        pos.apply_fill(
            fill_quantity=300,
            fill_price=180,
            execution_id="EXEC-001",
            order_id="ORD-001",
            source_event_id="EVT-001",
        )
        pos.apply_fill(
            fill_quantity=200,
            fill_price=182,
            execution_id="EXEC-002",
            order_id="ORD-001",
            source_event_id="EVT-002",
        )
        events = pos.collect_events()
        assert len(events) == 2


class TestOptimisticConcurrency:
    """Version tracking for optimistic concurrency."""

    def test_version_increments_on_fill(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA")
        assert pos.version == 1
        pos.apply_fill(fill_quantity=100, fill_price=180,
                       execution_id="E1", order_id="O1", source_event_id="EVT-1")
        assert pos.version == 2
        pos.apply_fill(fill_quantity=100, fill_price=182,
                       execution_id="E2", order_id="O2", source_event_id="EVT-2")
        assert pos.version == 3

    def test_version_increments_on_reduction(self) -> None:
        pos = Position.open_long("P1", "A1", "NVDA", quantity=500, average_price=180)
        assert pos.version == 1
        pos.apply_reduction(reduction_quantity=200, fill_price=185,
                            execution_id="E1", order_id="O1", source_event_id="EVT-1")
        assert pos.version == 2
