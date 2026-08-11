"""
Tests for LedgerExecutionEventConsumer — execution event processing,
ledger entry creation with debit/credit, idempotency, and full pipeline.

Coverage:
- ORDER_PARTIAL_FILL / ORDER_FILLED processing
- BUY accounting (credit cash)
- SELL accounting (debit cash)
- Fee and commission entries
- Fill delta tracking
- Idempotency (duplicate event, duplicate execution)
- Accounting state versioning
- Event ordering (stale event detection)
- Ledger event emission
- Lineage propagation (correlation/causation/lineage)
- Consumer retry / dead letter
- Support/non-support event filtering
"""

from __future__ import annotations

import pytest

from services.integration.event_envelope import DeliveryState, EventEnvelope
from services.integration.event_registry import EventRegistry
from services.ledger.consumers.execution_event_consumer import (
    LedgerExecutionEventConsumer,
)
from services.ledger.domain.ledger_entry import EntryType
from services.ledger.domain.ledger_event import (
    LedgerEntryCreatedEvent,
    LedgerEventType,
)
from services.ledger.exceptions import (
    EntryValidationError,
    SequenceGapError,
    StaleEventError,
)


# ── fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def registry() -> EventRegistry:
    reg = EventRegistry()
    reg.register_defaults()
    return reg


@pytest.fixture
def consumer(registry: EventRegistry) -> LedgerExecutionEventConsumer:
    return LedgerExecutionEventConsumer(registry)


# ── envelope helpers ───────────────────────────────────────────────

def _make_envelope(**overrides) -> EventEnvelope:
    """Create a test event envelope with sensible defaults."""
    event_id = overrides.pop("event_id", "EVT-001")
    payload = {
        "side": "BUY",
        "quantity": 1000,
        "filled_quantity": 1000,
        "ordered_quantity": 1000,
        "price": 180.0,
        "account_id": "ACC-001",
        "instrument_id": "NVDA",
        "symbol": "NVDA",
        "execution_id": f"EXEC-{event_id}",
        "cumulative_fill": 1000,
        "previous_fill": 0,
        "currency": "USD",
        "fee": 0.0,
        "commission": 0.0,
        "correlation_id": "CORR-001",
        "causation_id": "CAUS-001",
        "lineage_id": "LINE-001",
    }
    payload.update(overrides.pop("payload", {}))
    defaults = {
        "event_id": event_id,
        "event_type": "ORDER_FILLED",
        "event_version": 1,
        "aggregate_type": "ORDER",
        "aggregate_id": "ORD-001",
        "aggregate_version": 1,
        "producer": "OMS",
        "correlation_id": "CORR-001",
        "lineage_id": "LINE-001",
        "payload": payload,
    }
    defaults.update(overrides)
    return EventEnvelope.from_event(**defaults)


# ── Basic BUY processing ───────────────────────────────────────────

class TestConsumerBuyTrade:
    """BUY execution → Trade ledger entry."""

    def test_buy_creates_trade_entry(self, consumer: LedgerExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(event_id="EVT-001"))
        events = consumer.ledger_events
        assert len(events) == 1
        assert events[0].event_type == LedgerEventType.LEDGER_ENTRY_CREATED
        assert events[0].entry_type == EntryType.TRADE
        assert events[0].credit == 180000.0  # Cash credit (outflow)
        assert events[0].debit == 0.0
        assert events[0].amount == -180000.0

    def test_buy_with_fee_and_commission(self, consumer: LedgerExecutionEventConsumer) -> None:
        """BUY with fee + commission creates 3 entries."""
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001",
            payload={"fee": 10.0, "commission": 5.0},
        ))
        events = consumer.ledger_events
        assert len(events) == 3
        types = {e.entry_type for e in events}
        assert types == {EntryType.TRADE, EntryType.FEE, EntryType.COMMISSION}

    def test_buy_accounting_state_updated(self, consumer: LedgerExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(event_id="EVT-001"))
        state = consumer.get_accounting_state("ACC-001", "USD")
        assert state is not None
        assert state.credit_total == 180000.0
        assert state.balance == -180000.0

    def test_buy_balance_query(self, consumer: LedgerExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(event_id="EVT-001"))
        assert consumer.get_balance("ACC-001", "USD") == -180000.0


# ── SELL processing ────────────────────────────────────────────────

class TestConsumerSellTrade:
    """SELL execution → Trade ledger entry."""

    def test_sell_creates_trade_entry(self, consumer: LedgerExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001",
            payload={
                "side": "SELL", "quantity": 500, "filled_quantity": 500,
                "ordered_quantity": 500, "price": 185.0,
                "cumulative_fill": 500, "previous_fill": 0,
            },
        ))
        events = consumer.ledger_events
        assert len(events) == 1
        assert events[0].entry_type == EntryType.TRADE
        assert events[0].debit == 92500.0  # Cash debit (inflow)
        assert events[0].credit == 0.0
        assert events[0].amount == 92500.0

    def test_sell_balance_positive(self, consumer: LedgerExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001",
            payload={
                "side": "SELL", "quantity": 500, "filled_quantity": 500,
                "ordered_quantity": 500, "price": 185.0,
                "cumulative_fill": 500, "previous_fill": 0,
            },
        ))
        assert consumer.get_balance("ACC-001", "USD") == 92500.0

    def test_sell_with_fees(self, consumer: LedgerExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001",
            payload={
                "side": "SELL", "quantity": 1000, "filled_quantity": 1000,
                "ordered_quantity": 1000, "price": 185.0,
                "cumulative_fill": 1000, "previous_fill": 0,
                "fee": 10.0, "commission": 5.0,
            },
        ))
        # SELL: 185000 debit - 10 fee - 5 commission = 184985
        state = consumer.get_accounting_state("ACC-001", "USD")
        assert state is not None
        assert state.debit_total == 185015.0  # trade debit + fee debit + commission debit
        # fee and commission add to debit_total, trade adds to debit_total
        assert state.balance == 185015.0


# ── Partial fill delta ─────────────────────────────────────────────

class TestConsumerPartialFill:
    """ORDER_PARTIAL_FILL with fill delta tracking."""

    def test_partial_fill_creates_entry(self, consumer: LedgerExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001", event_type="ORDER_PARTIAL_FILL",
            aggregate_version=1,
            payload={
                "quantity": 300, "filled_quantity": 300, "ordered_quantity": 1000,
                "price": 179.0, "cumulative_fill": 300, "previous_fill": 0,
            },
        ))
        events = consumer.ledger_events
        assert len(events) == 1
        assert events[0].entry_type == EntryType.TRADE
        assert events[0].credit == 53700.0  # 300 * 179

    def test_fill_delta_tracked(self, consumer: LedgerExecutionEventConsumer) -> None:
        """Fill delta is tracked per order for cumulative fill calculation."""
        # First fill: 300
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001", event_type="ORDER_PARTIAL_FILL",
            aggregate_version=1,
            payload={
                "quantity": 300, "filled_quantity": 300, "ordered_quantity": 1000,
                "price": 179.0, "cumulative_fill": 300, "previous_fill": 0,
            },
        ))

        # Second fill: cumulative 1000
        consumer.on_envelope(_make_envelope(
            event_id="EVT-002", event_type="ORDER_FILLED",
            aggregate_version=2,
            payload={
                "quantity": 700, "filled_quantity": 700, "ordered_quantity": 1000,
                "price": 181.0, "cumulative_fill": 1000, "previous_fill": 300,
            },
        ))

        fill_state = consumer.get_fill_state("ORD-001")
        assert fill_state is not None
        assert fill_state.cumulative_fill == 1000.0
        assert fill_state.last_version == 2

    def test_multiple_partial_fills(self, consumer: LedgerExecutionEventConsumer) -> None:
        # Fill 1: 200 @ 180
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001", event_type="ORDER_PARTIAL_FILL",
            aggregate_version=1,
            payload={
                "quantity": 200, "filled_quantity": 200, "ordered_quantity": 1000,
                "price": 180.0, "cumulative_fill": 200, "previous_fill": 0,
            },
        ))
        # Fill 2: 300 @ 181 (cumulative = 500)
        consumer.on_envelope(_make_envelope(
            event_id="EVT-002", event_type="ORDER_PARTIAL_FILL",
            aggregate_version=2,
            payload={
                "quantity": 300, "filled_quantity": 300, "ordered_quantity": 1000,
                "price": 181.0, "cumulative_fill": 500, "previous_fill": 200,
            },
        ))
        # Fill 3: 500 @ 182 (cumulative = 1000)
        consumer.on_envelope(_make_envelope(
            event_id="EVT-003", event_type="ORDER_FILLED",
            aggregate_version=3,
            payload={
                "quantity": 500, "filled_quantity": 500, "ordered_quantity": 1000,
                "price": 182.0, "cumulative_fill": 1000, "previous_fill": 500,
            },
        ))
        assert len(consumer.ledger_events) == 3
        state = consumer.get_accounting_state("ACC-001", "USD")
        assert state is not None
        # 200*180 + 300*181 + 500*182 = 36000 + 54300 + 91000 = 181300
        assert state.credit_total == 181300.0


# ── Idempotency ────────────────────────────────────────────────────

class TestConsumerIdempotency:
    """Duplicate events and executions MUST NOT create duplicate entries."""

    def test_duplicate_event_no_duplicate_entry(self, consumer: LedgerExecutionEventConsumer) -> None:
        env = _make_envelope(event_id="EVT-001")
        consumer.on_envelope(env)
        assert len(consumer.ledger_events) == 1

        consumer.on_envelope(env)
        assert len(consumer.ledger_events) == 1  # Still 1

    def test_duplicate_execution_id_no_duplicate(self, consumer: LedgerExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(event_id="EVT-001"))  # execution EXEC-EVT-001

        # Same execution_id via different event_id
        consumer.on_envelope(_make_envelope(
            event_id="EVT-002",
            payload={"execution_id": "EXEC-EVT-001"},
        ))
        # No new entries added
        assert len(consumer.ledger_events) == 1

    def test_different_executions_different_entries(self, consumer: LedgerExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(event_id="EVT-001"))
        consumer.on_envelope(_make_envelope(
            event_id="EVT-002",
            payload={"execution_id": "EXEC-EVT-002", "order_id": "ORD-002"},
        ))
        assert len(consumer.ledger_events) == 2

    def test_delivery_state_is_delivered_after_processing(self, consumer: LedgerExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(event_id="EVT-001"))
        assert consumer.get_delivery_state("EVT-001") == DeliveryState.DELIVERED


# ── Ordering / stale events ────────────────────────────────────────

class TestConsumerOrdering:
    """Event ordering — stale events and sequence gaps."""

    def test_stale_event_skipped(self, consumer: LedgerExecutionEventConsumer) -> None:
        # First: version 2
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001", aggregate_version=2,
            payload={
                "quantity": 500, "filled_quantity": 500, "ordered_quantity": 1000,
                "price": 180.0, "cumulative_fill": 500, "previous_fill": 0,
            },
        ))
        # Second: version 1 (stale)
        consumer.on_envelope(_make_envelope(
            event_id="EVT-002", aggregate_version=1,
            payload={
                "quantity": 300, "filled_quantity": 300, "ordered_quantity": 1000,
                "price": 179.0, "cumulative_fill": 300, "previous_fill": 0,
            },
        ))
        # Only the first event's entry should exist
        assert len(consumer.ledger_events) == 1

    def test_sequence_gap(self, consumer: LedgerExecutionEventConsumer) -> None:
        # First: version 1
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001", aggregate_version=1,
            payload={
                "quantity": 300, "filled_quantity": 300, "ordered_quantity": 1000,
                "price": 180.0, "cumulative_fill": 300, "previous_fill": 0,
            },
        ))
        # Gap: version 3 (missing version 2)
        with pytest.raises(SequenceGapError):
            consumer.on_envelope(_make_envelope(
                event_id="EVT-003", aggregate_version=3,
                payload={
                    "quantity": 700, "filled_quantity": 700, "ordered_quantity": 1000,
                    "price": 181.0, "cumulative_fill": 1000, "previous_fill": 300,
                },
            ))


# ── Lineage propagation ────────────────────────────────────────────

class TestConsumerLineage:
    """Correlation / causation / lineage propagation to ledger events."""

    def test_lineage_propagated_to_events(self, consumer: LedgerExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001",
            payload={
                "correlation_id": "CORR-STRATEGY-001",
                "causation_id": "CAUS-ORDER-001",
                "lineage_id": "LINE-STRATEGY-001",
            },
        ))
        event = consumer.ledger_events[0]
        assert event.correlation_id == "CORR-STRATEGY-001"
        assert event.causation_id == "CAUS-ORDER-001"
        assert event.lineage_id == "LINE-STRATEGY-001"

    def test_envelope_lineage_used_as_fallback(self, consumer: LedgerExecutionEventConsumer) -> None:
        """If payload lacks lineage, envelope-level lineage is used."""
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001",
            correlation_id="CORR-ENV-001",
            lineage_id="LINE-ENV-001",
            payload={
                "correlation_id": "",  # empty in payload
                "causation_id": "",
                "lineage_id": "",
            },
        ))
        event = consumer.ledger_events[0]
        assert event.correlation_id == "CORR-ENV-001"
        assert event.lineage_id == "LINE-ENV-001"


# ── Event filtering ────────────────────────────────────────────────

class TestConsumerEventFiltering:
    """Unsupported events are skipped."""

    def test_order_created_is_skipped(self, consumer: LedgerExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-SKIP", event_type="ORDER_CREATED", aggregate_version=1,
        ))
        assert len(consumer.ledger_events) == 0

    def test_order_rejected_is_skipped(self, consumer: LedgerExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-SKIP", event_type="ORDER_REJECTED", aggregate_version=1,
        ))
        assert len(consumer.ledger_events) == 0


# ── Validation failures ────────────────────────────────────────────

class TestConsumerValidation:
    """Invalid payloads cause RETRYING state."""

    def test_invalid_quantity_zero(self, consumer: LedgerExecutionEventConsumer) -> None:
        with pytest.raises(EntryValidationError):
            consumer.on_envelope(_make_envelope(
                event_id="EVT-FAIL", aggregate_version=1,
                payload={"quantity": 0, "filled_quantity": 0, "price": 180.0,
                         "cumulative_fill": 0, "previous_fill": 0},
            ))
        state = consumer.get_delivery_state("EVT-FAIL")
        assert state == DeliveryState.RETRYING

    def test_missing_account_id_still_creates_entry(self, consumer: LedgerExecutionEventConsumer) -> None:
        """When account_id is missing from payload, aggregate_id is used."""
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001",
            aggregate_id="ACC-VIA-AGG",
            payload={"account_id": "", "quantity": 100, "filled_quantity": 100,
                     "ordered_quantity": 100, "price": 180.0,
                     "cumulative_fill": 100, "previous_fill": 0},
        ))
        events = consumer.ledger_events
        assert len(events) == 1
        assert events[0].account_id == "ACC-VIA-AGG"


# ── Multi-entry consistency ────────────────────────────────────────

class TestConsumerMultiEntry:
    """Multiple entries from the same execution maintain consistency."""

    def test_single_execution_multiple_entries(self, consumer: LedgerExecutionEventConsumer) -> None:
        """One execution with fee + commission → 3 separate ledger entries."""
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001",
            payload={"fee": 10.0, "commission": 5.0},
        ))
        assert len(consumer.ledger_events) == 3
        trade = consumer.get_ledger_events_by_type(LedgerEventType.LEDGER_ENTRY_CREATED)
        assert len(trade) == 3

    def test_entry_types_distinct(self, consumer: LedgerExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001",
            payload={"fee": 10.0, "commission": 5.0},
        ))
        types = [e.entry_type for e in consumer.ledger_events]
        assert types.count(EntryType.TRADE) == 1
        assert types.count(EntryType.FEE) == 1
        assert types.count(EntryType.COMMISSION) == 1

    def test_all_entries_share_execution_id(self, consumer: LedgerExecutionEventConsumer) -> None:
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001",
            payload={"fee": 10.0, "commission": 5.0, "execution_id": "EXEC-SHARED"},
        ))
        for event in consumer.ledger_events:
            assert event.execution_id == "EXEC-SHARED"

    def test_balance_reflects_all_entries(self, consumer: LedgerExecutionEventConsumer) -> None:
        """Balance reflects trade + fee + commission for a BUY.

        BUY: Trade credits cash 180000, Fee debits 10, Commission debits 5.
        balance = debit_total - credit_total = 15 - 180000 = -179985
        """
        consumer.on_envelope(_make_envelope(
            event_id="EVT-001",
            payload={
                "quantity": 1000, "filled_quantity": 1000, "ordered_quantity": 1000,
                "price": 180.0, "fee": 10.0, "commission": 5.0,
                "cumulative_fill": 1000, "previous_fill": 0,
            },
        ))
        state = consumer.get_accounting_state("ACC-001", "USD")
        assert state is not None
        assert state.debit_total == 15.0  # fee + commission
        assert state.credit_total == 180000.0  # trade
        assert state.balance == -179985.0


# ── Dead letter ────────────────────────────────────────────────────

class TestConsumerDeadLetter:
    """Dead letter after exceeding max retries."""

    def test_dead_letter_after_max_retries(self, consumer: LedgerExecutionEventConsumer) -> None:
        consumer._max_retries = 3
        event_id = "EVT-DEAD"
        env = _make_envelope(
            event_id=event_id,
            aggregate_version=1,
            payload={"quantity": 0, "filled_quantity": 0, "price": 0,
                     "cumulative_fill": 0, "previous_fill": 0},
        )

        # First 3 attempts → RETRYING (re-raised)
        for _ in range(3):
            with pytest.raises(EntryValidationError):
                consumer.on_envelope(env)

        # Fourth attempt → DEAD_LETTER (no re-raise)
        consumer.on_envelope(env)

        assert event_id in consumer._dead_letters
        assert consumer.get_delivery_state(event_id) == DeliveryState.DEAD_LETTER
