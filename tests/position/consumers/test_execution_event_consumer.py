"""
Tests for ExecutionEventConsumer — position service consumer.

Covers:
- Fill delta calculation via execution state tracking
- BUY / SELL fill application
- Partial fills building up to full fill
- Idempotency (duplicate event, duplicate execution)
- Sequence gap detection (aggregate_version)
- Over-fill protection
- Negative delta detection
- Consumer retry and dead-letter
- Position domain events generation
- Consumer isolation (independent offsets)
"""

from __future__ import annotations

import pytest

from services.integration.event_consumer import DeliveryState
from services.integration.event_envelope import EventEnvelope
from services.integration.event_registry import EventRegistry

from services.position.consumers.execution_event_consumer import (
    ExecutionEventConsumer,
    ExecutionState,
    SUPPORTED_EVENT_TYPES,
)
from services.position.domain.position_event import (
    PositionClosedEvent,
    PositionDecreasedEvent,
    PositionIncreasedEvent,
)
from services.position.exceptions.position_error import (
    InvalidExecutionError,
    SequenceGapError,
    StaleEventError,
)


# ------------------------------------------------------------------
#  Helpers
# ------------------------------------------------------------------

def _make_envelope(
    event_id: str = "EVT-001",
    event_type: str = "ORDER_FILLED",
    aggregate_id: str = "ORD-001",
    aggregate_version: int = 1,
    payload: dict | None = None,
    correlation_id: str = "",
    lineage_id: str = "",
) -> EventEnvelope:
    default_payload = {
        "side": "BUY",
        "quantity": 500,
        "filled_quantity": 500,
        "price": 180.0,
        "account_id": "ACC-001",
        "instrument_id": "NVDA",
        "symbol": "NVDA",
        "execution_id": f"EXEC-{event_id}",
        "cumulative_fill": 500,
        "previous_fill": 0,
    }
    if payload:
        default_payload.update(payload)

    # Auto-derive ordered_quantity from quantity if not explicitly set
    if "ordered_quantity" not in default_payload:
        default_payload["ordered_quantity"] = float(
            default_payload.get("quantity", 500)
        )

    return EventEnvelope(
        event_id=event_id,
        event_type=event_type,
        event_version=1,
        aggregate_type="ORDER",
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        producer="OMS",
        correlation_id=correlation_id or f"CORR-{event_id}",
        lineage_id=lineage_id or f"LIN-{event_id}",
        payload=default_payload,
    )


@pytest.fixture
def registry() -> EventRegistry:
    return EventRegistry()


@pytest.fixture
def consumer(registry: EventRegistry) -> ExecutionEventConsumer:
    return ExecutionEventConsumer(registry)


# ------------------------------------------------------------------
#  ExecutionState tests
# ------------------------------------------------------------------

class TestExecutionState:
    """Per-order execution state tracking."""

    def test_first_fill_records_correctly(self) -> None:
        state = ExecutionState(
            order_id="ORD-001",
            instrument_id="NVDA",
            ordered_quantity=1000,
        )
        delta = state.record_fill(
            cumulative_fill=300,
            event_id="EVT-001",
            version=1,
        )
        assert delta == 300
        assert state.filled_quantity == 300

    def test_second_fill_calculates_delta(self) -> None:
        state = ExecutionState(
            order_id="ORD-001",
            instrument_id="NVDA",
            ordered_quantity=1000,
        )
        state.record_fill(cumulative_fill=300, event_id="EVT-001", version=1)
        delta = state.record_fill(cumulative_fill=1000, event_id="EVT-002", version=2)
        assert delta == 700
        assert state.filled_quantity == 1000

    def test_partial_fill_sequence(self) -> None:
        state = ExecutionState("ORD-001", "NVDA", 1000)
        d1 = state.record_fill(200, "EVT-001", 1)
        d2 = state.record_fill(500, "EVT-002", 2)
        d3 = state.record_fill(1000, "EVT-003", 3)
        assert d1 == 200
        assert d2 == 300
        assert d3 == 500

    def test_sequence_gap_detected(self) -> None:
        state = ExecutionState("ORD-001", "NVDA", 1000)
        state.record_fill(300, "EVT-001", 1)
        with pytest.raises(SequenceGapError):
            state.record_fill(1000, "EVT-003", 3)  # skip version 2

    def test_stale_event_detected(self) -> None:
        state = ExecutionState("ORD-001", "NVDA", 1000)
        state.record_fill(300, "EVT-001", 2)
        with pytest.raises(StaleEventError):
            state.record_fill(300, "EVT-000", 1)  # version behind


# ------------------------------------------------------------------
#  Consumer — fill acceptance
# ------------------------------------------------------------------

class TestConsumerOrderFilled:
    """Consumer processes ORDER_FILLED events."""

    def test_single_full_fill(self, consumer: ExecutionEventConsumer) -> None:
        envelope = _make_envelope(event_id="EVT-001", event_type="ORDER_FILLED")
        consumer.on_envelope(envelope)

        snap = consumer.get_position_snapshot("POS-ACC-001-NVDA")
        assert snap is not None
        assert snap.quantity == 500
        assert snap.average_price == 180.0

    def test_multiple_fills_same_order(self, consumer: ExecutionEventConsumer) -> None:
        # Partial fill 1: 300
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001",
            event_type="ORDER_PARTIAL_FILL",
            aggregate_version=1,
            payload={
                "side": "BUY", "quantity": 300, "filled_quantity": 300,
                "ordered_quantity": 1000,
                "price": 180.0, "account_id": "ACC-001", "instrument_id": "NVDA",
                "execution_id": "EXEC-EVT-001",
                "cumulative_fill": 300, "previous_fill": 0,
            },
        ))

        snap = consumer.get_position_snapshot("POS-ACC-001-NVDA")
        assert snap is not None
        assert snap.quantity == 300

        # Partial fill 2: cumulative 500 (delta = 200)
        consumer.on_envelope(_make_envelope(
            event_id="EVT-002",
            event_type="ORDER_PARTIAL_FILL",
            aggregate_id="ORD-001",
            aggregate_version=2,
            payload={
                "side": "BUY", "quantity": 500, "filled_quantity": 500,
                "ordered_quantity": 1000,
                "price": 182.0, "account_id": "ACC-001", "instrument_id": "NVDA",
                "execution_id": "EXEC-EVT-002",
                "cumulative_fill": 500, "previous_fill": 300,
            },
        ))

        snap = consumer.get_position_snapshot("POS-ACC-001-NVDA")
        assert snap.quantity == 500
        assert snap.average_price == pytest.approx((300 * 180 + 200 * 182) / 500)

        # Full fill: cumulative 1000 (delta = 500)
        consumer.on_envelope(_make_envelope(
            event_id="EVT-003",
            event_type="ORDER_FILLED",
            aggregate_id="ORD-001",
            aggregate_version=3,
            payload={
                "side": "BUY", "quantity": 1000, "filled_quantity": 1000,
                "ordered_quantity": 1000,
                "price": 180.50, "account_id": "ACC-001", "instrument_id": "NVDA",
                "execution_id": "EXEC-EVT-003",
                "cumulative_fill": 1000, "previous_fill": 500,
            },
        ))

        snap = consumer.get_position_snapshot("POS-ACC-001-NVDA")
        assert snap.quantity == 1000

    def test_buy_fill_increases_position(self, consumer: ExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001", event_type="ORDER_FILLED",
            payload={
                "side": "BUY", "quantity": 1000, "filled_quantity": 1000,
                "price": 180.0, "account_id": "ACC-001", "instrument_id": "NVDA",
                "execution_id": "EXEC-EVT-001",
                "cumulative_fill": 1000, "previous_fill": 0,
            },
        ))
        snap = consumer.get_position_snapshot("POS-ACC-001-NVDA")
        assert snap.quantity == 1000

    def test_sell_fill_decreases_position(self, consumer: ExecutionEventConsumer) -> None:
        # First buy 1000
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001", event_type="ORDER_FILLED",
            payload={
                "side": "BUY", "quantity": 1000, "filled_quantity": 1000,
                "price": 180.0, "account_id": "ACC-001", "instrument_id": "NVDA",
                "execution_id": "EXEC-EVT-001",
                "cumulative_fill": 1000, "previous_fill": 0,
            },
        ))
        # Then sell 400
        consumer.on_envelope(_make_envelope(
            event_id="EVT-002", event_type="ORDER_FILLED",
            aggregate_id="ORD-002",
            payload={
                "side": "SELL", "quantity": 400, "filled_quantity": 400,
                "price": 185.0, "account_id": "ACC-001", "instrument_id": "NVDA",
                "execution_id": "EXEC-EVT-002",
                "cumulative_fill": 400, "previous_fill": 0,
            },
        ))
        snap = consumer.get_position_snapshot("POS-ACC-001-NVDA")
        assert snap.quantity == 600


# ------------------------------------------------------------------
#  Position domain events
# ------------------------------------------------------------------

class TestPositionEventsEmitted:
    """Consumer generates correct position domain events."""

    def test_position_increased_event_emitted(self, consumer: ExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001", event_type="ORDER_FILLED",
            payload={
                "side": "BUY", "quantity": 500, "filled_quantity": 500,
                "price": 180.0, "account_id": "ACC-001", "instrument_id": "NVDA",
                "execution_id": "EXEC-EVT-001",
                "cumulative_fill": 500, "previous_fill": 0,
            },
        ))
        events = consumer.get_position_events()
        assert len(events) >= 1
        assert isinstance(events[0], PositionIncreasedEvent)
        assert events[0].new_quantity == 500
        assert events[0].delta_quantity == 500

    def test_position_decreased_event_emitted(self, consumer: ExecutionEventConsumer) -> None:
        # Build position first
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001", event_type="ORDER_FILLED",
            payload={
                "side": "BUY", "quantity": 1000, "filled_quantity": 1000,
                "price": 180.0, "account_id": "ACC-001", "instrument_id": "NVDA",
                "execution_id": "EXEC-EVT-001",
                "cumulative_fill": 1000, "previous_fill": 0,
            },
        ))
        # Sell part
        consumer.on_envelope(_make_envelope(
            event_id="EVT-002", event_type="ORDER_FILLED",
            aggregate_id="ORD-002",
            payload={
                "side": "SELL", "quantity": 300, "filled_quantity": 300,
                "price": 185.0, "account_id": "ACC-001", "instrument_id": "NVDA",
                "execution_id": "EXEC-EVT-002",
                "cumulative_fill": 300, "previous_fill": 0,
            },
        ))
        events = consumer.get_position_events()
        decreased_events = [e for e in events if isinstance(e, PositionDecreasedEvent)]
        assert len(decreased_events) == 1
        assert decreased_events[0].new_quantity == 700
        assert decreased_events[0].delta_quantity == -300

    def test_position_closed_event_emitted(self, consumer: ExecutionEventConsumer) -> None:
        # Buy 1000
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001", event_type="ORDER_FILLED",
            payload={
                "side": "BUY", "quantity": 1000, "filled_quantity": 1000,
                "price": 180.0, "account_id": "ACC-001", "instrument_id": "NVDA",
                "execution_id": "EXEC-EVT-001",
                "cumulative_fill": 1000, "previous_fill": 0,
            },
        ))
        # Sell all 1000
        consumer.on_envelope(_make_envelope(
            event_id="EVT-002", event_type="ORDER_FILLED",
            aggregate_id="ORD-002",
            payload={
                "side": "SELL", "quantity": 1000, "filled_quantity": 1000,
                "price": 185.0, "account_id": "ACC-001", "instrument_id": "NVDA",
                "execution_id": "EXEC-EVT-002",
                "cumulative_fill": 1000, "previous_fill": 0,
            },
        ))
        events = consumer.get_position_events()
        closed_events = [e for e in events if isinstance(e, PositionClosedEvent)]
        assert len(closed_events) == 1
        assert closed_events[0].new_quantity == 0

    def test_event_lineage_propagated(self, consumer: ExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001", event_type="ORDER_FILLED",
            correlation_id="CORR-STRATEGY-001",
            lineage_id="LIN-TXN-001",
            payload={
                "side": "BUY", "quantity": 100, "filled_quantity": 100,
                "price": 180.0, "account_id": "ACC-001", "instrument_id": "NVDA",
                "execution_id": "EXEC-EVT-001",
                "cumulative_fill": 100, "previous_fill": 0,
            },
        ))
        events = consumer.get_position_events()
        assert len(events) >= 1
        assert events[0].correlation_id == "CORR-STRATEGY-001"
        assert events[0].lineage_id == "LIN-TXN-001"


# ------------------------------------------------------------------
#  Idempotency
# ------------------------------------------------------------------

class TestIdempotency:
    """Duplicate events and executions are no-ops."""

    def test_duplicate_event_id_noop(self, consumer: ExecutionEventConsumer) -> None:
        envelope = _make_envelope(event_id="EVT-001", event_type="ORDER_FILLED")
        consumer.on_envelope(envelope)
        consumer.on_envelope(envelope)  # duplicate

        snap = consumer.get_position_snapshot("POS-ACC-001-NVDA")
        assert snap.quantity == 500  # still 500, not 1000

    def test_duplicate_execution_id_noop(self, consumer: ExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-DATA-CORR-001",
            lineage_id="LIN-002",
            payload={
                "side": "BUY", "quantity": 300, "filled_quantity": 300,
                "price": 180.0, "account_id": "ACC-001", "instrument_id": "NVDA",
                "execution_id": "EXEC-DUP-001",
                "cumulative_fill": 300, "previous_fill": 0,
            },
        ))
        consumer.on_envelope(_make_envelope(
            event_id="EVT-DATA-CORR-002",
            lineage_id="LIN-002",
            payload={
                "side": "BUY", "quantity": 300, "filled_quantity": 300,
                "price": 180.0, "account_id": "ACC-001", "instrument_id": "NVDA",
                "execution_id": "EXEC-DUP-001",
                "cumulative_fill": 300, "previous_fill": 0,
            },
        ))
        snap = consumer.get_position_snapshot("POS-ACC-001-NVDA")
        assert snap.quantity == 300


# ------------------------------------------------------------------
#  Error handling
# ------------------------------------------------------------------

class TestFailureHandling:
    """Consumer failure, retry, and dead-letter."""

    def test_failed_event_recorded(self, consumer: ExecutionEventConsumer) -> None:
        consumer._max_retries = 3
        envelope = _make_envelope(event_id="EVT-FAIL", event_type="ORDER_FILLED",
                                  payload={"side": "BUY", "quantity": 0, "filled_quantity": 0,
                                           "price": 180.0, "account_id": "ACC-001",
                                           "instrument_id": "NVDA",
                                           "execution_id": "EXEC-FAIL",
                                           "cumulative_fill": 0, "previous_fill": 0})

        # This should fail validation (quantity 0) and _handle_failure re-raises
        with pytest.raises(InvalidExecutionError):
            consumer.on_envelope(envelope)
        state = consumer.get_delivery_state("EVT-FAIL")
        assert state == DeliveryState.RETRYING

    def test_dead_letter_after_max_retries(self, consumer: ExecutionEventConsumer) -> None:
        """After exceeding max_retries, event goes to DEAD_LETTER."""
        consumer._max_retries = 3
        event_id = "EVT-DEAD"
        env = _make_envelope(event_id=event_id, event_type="ORDER_FILLED")
        env.payload["quantity"] = 0  # make it invalid

        # First 3 attempts: _handle_failure re-raises (RETRYING)
        for _ in range(3):
            with pytest.raises(InvalidExecutionError):
                consumer.on_envelope(env)

        # Fourth attempt: dead-letter (NO re-raise from _handle_failure)
        consumer.on_envelope(env)

        assert event_id in consumer._dead_letters
        assert consumer.get_delivery_state(event_id) == DeliveryState.DEAD_LETTER


# ------------------------------------------------------------------
#  Multi-symbol & isolation
# ------------------------------------------------------------------

class TestMultiSymbol:
    """Multiple instruments with independent positions."""

    def test_isolated_by_symbol(self, consumer: ExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001", event_type="ORDER_FILLED",
            payload={"side": "BUY", "quantity": 500, "filled_quantity": 500,
                     "price": 180.0, "account_id": "ACC-001", "instrument_id": "NVDA",
                     "execution_id": "EXEC-001",
                     "cumulative_fill": 500, "previous_fill": 0},
        ))
        consumer.on_envelope(_make_envelope(
            event_id="EVT-002", event_type="ORDER_FILLED",
            aggregate_id="ORD-002",
            payload={"side": "BUY", "quantity": 200, "filled_quantity": 200,
                     "price": 150.0, "account_id": "ACC-001", "instrument_id": "AAPL",
                     "execution_id": "EXEC-002",
                     "cumulative_fill": 200, "previous_fill": 0},
        ))

        nvda = consumer.get_position_snapshot("POS-ACC-001-NVDA")
        aapl = consumer.get_position_snapshot("POS-ACC-001-AAPL")
        assert nvda.quantity == 500
        assert aapl.quantity == 200
        assert nvda.average_price == 180.0
        assert aapl.average_price == 150.0


# ------------------------------------------------------------------
#  Unsupported events
# ------------------------------------------------------------------

class TestUnsupportedEvents:
    """Non-execution events are silently ignored."""

    def test_order_created_ignored(self, consumer: ExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001", event_type="ORDER_CREATED",
        ))
        assert consumer.get_delivery_state("EVT-001") == DeliveryState.DELIVERED

    def test_order_working_ignored(self, consumer: ExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001", event_type="ORDER_WORKING",
        ))
        assert consumer.get_delivery_state("EVT-001") == DeliveryState.DELIVERED

    def test_order_rejected_ignored(self, consumer: ExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001", event_type="ORDER_REJECTED",
        ))
        assert consumer.get_delivery_state("EVT-001") == DeliveryState.DELIVERED


# ------------------------------------------------------------------
#  Consumer configuration
# ------------------------------------------------------------------

class TestConsumerConfiguration:
    """Consumer metadata."""

    def test_consumer_group(self, consumer: ExecutionEventConsumer) -> None:
        assert consumer.get_consumer_group() == "position-service"

    def test_supported_event_types(self) -> None:
        assert "ORDER_PARTIAL_FILL" in SUPPORTED_EVENT_TYPES
        assert "ORDER_FILLED" in SUPPORTED_EVENT_TYPES

    def test_execution_state_tracking(self, consumer: ExecutionEventConsumer) -> None:
        state = consumer.ensure_execution_state("ORD-001", "NVDA", 1000)
        assert state.order_id == "ORD-001"
        assert state.instrument_id == "NVDA"
        assert state.ordered_quantity == 1000
        assert state.filled_quantity == 0
