"""
Ledger Execution Event Consumer.

Processes ORDER_FILLED / ORDER_PARTIAL_FILL events and produces
immutable ledger entries (Trade, Fee, Commission) with full
double-entry accounting.

Pipeline:

    Event
     ↓
    Envelope Check
     ↓
    Event Type Filter
     ↓
    Idempotency (event_id + execution_id)
     ↓
    Build RecordExecutionCommand
     ↓
    Validate Command
     ↓
    Build Accounting Entries (Trade / Fee / Commission)
     ↓
    Double-Entry Validation
     ↓
    Apply to AccountingState
     ↓
    Emit LEDGER_ENTRY_CREATED events
     ↓
    Update Projection
     ↓
    Mark Delivered

Key principles:
- Ledger Entry is IMMUTABLE (no UPDATE, corrections are new entries)
- Trade / Fee / Commission are separate entries for auditability
- Double-entry: each accounting batch must balance (debit == credit)
- Idempotency per (account_id, execution_id, entry_type)
- Consumer group isolation: ledger-service (independent of position-service)
"""

from typing import Dict, List, Optional, Set

from ...integration.event_consumer import DeliveryState, EventConsumer
from ...integration.event_envelope import EventEnvelope
from ...integration.event_registry import EventRegistry
from ..commands.record_execution import RecordExecutionCommand
from ..domain.accounting_state import AccountingState
from ..domain.ledger_entry import (
    AccountingBatch,
    EntryType,
)
from ..domain.ledger_event import (
    LedgerEntryCreatedEvent,
    LedgerEvent,
    LedgerEventType,
)
from ..exceptions import (
    AccountingConflictError,
    DuplicateEntryError,
    EntryValidationError,
    SequenceGapError,
    StaleEventError,
)


# ── Supported event types ──────────────────────────────────────────
SUPPORTED_EVENT_TYPES = frozenset({
    "ORDER_PARTIAL_FILL",
    "ORDER_FILLED",
})


# ── Fill tracking per order ────────────────────────────────────────
class FillState:
    """Tracks cumulative fill for a single order to compute deltas."""

    def __init__(self, order_id: str, instrument_id: str, ordered_quantity: float):
        self.order_id = order_id
        self.instrument_id = instrument_id
        self.ordered_quantity = ordered_quantity
        self.cumulative_fill: float = 0.0
        self.last_version: int = 0
        self.last_event_id: str = ""

    def record_fill(
        self, cumulative_fill: float, event_id: str, version: int
    ) -> float:
        """
        Record a fill event and return the delta quantity.

        Raises:
            SequenceGapError: version gap detected
            StaleEventError: version already applied
        """
        if version <= self.last_version and self.last_version > 0:
            raise StaleEventError(
                aggregate_id=self.order_id,
                current_version=self.last_version,
                event_version=version,
            )
        if version > self.last_version + 1 and self.last_version > 0:
            raise SequenceGapError(
                aggregate_id=self.order_id,
                expected_version=self.last_version + 1,
                received_version=version,
            )

        delta = cumulative_fill - self.cumulative_fill
        self.cumulative_fill = cumulative_fill
        self.last_version = version
        self.last_event_id = event_id
        return max(delta, 0.0)


# ── Consumer ────────────────────────────────────────────────────────

class LedgerExecutionEventConsumer(EventConsumer):
    """
    Consumes execution events and produces immutable ledger entries.

    Each execution generates up to 3 entries:
    - TRADE      (trade notional)
    - FEE        (trading fees, if any)
    - COMMISSION (broker commission, if any)

    All entries within a single execution form an AccountingBatch
    that MUST be balanced (total_debit == total_credit).
    """

    # ── construction ────────────────────────────────────────────────

    def __init__(self, registry: Optional[EventRegistry] = None):
        super().__init__(registry, consumer_group="ledger-service")

        # ── per-order fill tracking ─────────────────────────────
        self._fill_states: Dict[str, FillState] = {}

        # ── idempotency ─────────────────────────────────────────
        self._processed_executions: Set[str] = set()

        # ── accounting state per (account, currency) ────────────
        self._accounting_states: Dict[str, AccountingState] = {}

        # ── ledger event log ────────────────────────────────────
        self._ledger_events: List[LedgerEvent] = []

    # ── abstract method ────────────────────────────────────────────

    def handle(self, envelope: EventEnvelope) -> None:
        """Delegate to on_envelope for custom pipeline processing."""
        self.on_envelope(envelope)

    # ── main entry point ───────────────────────────────────────────

    def on_envelope(self, envelope: EventEnvelope) -> None:
        """Process a single execution event from the event bus."""
        event_type = envelope.event_type
        event_id = envelope.event_id

        # ── filter: only supported event types ──────────────────
        if event_type not in SUPPORTED_EVENT_TYPES:
            self._mark_delivered(event_id)
            return

        # ── idempotency: duplicate event ────────────────────────
        if not self._check_idempotency(event_id):
            return

        # ── basic envelope check ────────────────────────────────
        if not envelope.event_id or not envelope.aggregate_id:
            self._mark_processed(event_id)
            return

        try:
            # 1.  Extract side
            payload = envelope.payload or {}
            side = self._extract_side(payload)
            if side is None:
                self._mark_delivered(event_id)
                return

            # 2.  Build command
            command = self._build_command(envelope, side)

            # 3.  Validate command
            command.validate()

            # 4.  Check execution duplicate
            if self._has_execution(command.execution_id, command.source_event_id):
                self._mark_delivered(event_id)
                return

            # 5.  Track fill delta
            delta = self._track_fill(command, event_id, envelope)
            if delta is None:
                # Stale event, mark delivered
                self._mark_delivered(event_id)
                return
            command.delta = delta

            # 6.  Build entries (Trade / Fee / Commission)
            command.build_entries()

            # 7.  Build accounting batch and validate double-entry
            batch = command.build_batch()

            # 8.  Apply to accounting state
            self._apply_batch(batch, command, event_id)

            # 9.  Record execution as processed
            self._mark_execution(command.execution_id)

            # 10. Mark as delivered
            self._mark_delivered(event_id)

        except EntryValidationError as exc:
            self._handle_failure(envelope, exc)

    # ── side extraction ────────────────────────────────────────────

    def _extract_side(self, payload: dict) -> Optional[str]:
        """Extract BUY/SELL side from event payload."""
        side = str(payload.get("side", "")).upper().strip()
        if side in ("BUY", "SELL"):
            return side
        return None

    # ── command construction ───────────────────────────────────────

    def _build_command(
        self, envelope: EventEnvelope, side: str
    ) -> RecordExecutionCommand:
        """Build a RecordExecutionCommand from an event envelope."""
        payload = envelope.payload or {}

        quantity = float(payload.get("quantity", payload.get("filled_quantity", 0)))
        price = float(payload.get("price", 0))

        fee = float(payload.get("fee", 0))
        commission = float(payload.get("commission", payload.get("commission_fee", 0)))

        account_id = str(payload.get("account_id") or envelope.aggregate_id)
        instrument_id = str(payload.get("instrument_id") or payload.get("symbol", ""))
        currency = str(payload.get("currency") or "USD")

        execution_id = str(payload.get("execution_id") or f"EXEC-{envelope.event_id}")
        order_id = str(payload.get("order_id") or envelope.aggregate_id)
        ordered_qty = float(
            payload.get("ordered_quantity") or payload.get("order_quantity") or quantity
        )
        cumulative_fill = float(payload.get("cumulative_fill") or quantity)
        previous_fill = float(payload.get("previous_fill") or 0)

        return RecordExecutionCommand(
            account_id=account_id,
            instrument_id=instrument_id,
            side=side,
            fill_quantity=quantity,
            fill_price=price,
            order_id=order_id,
            execution_id=execution_id,
            source_event_id=envelope.event_id,
            currency=currency,
            fee=fee,
            commission=commission,
            ordered_quantity=ordered_qty,
            cumulative_fill=cumulative_fill,
            previous_cumulative_fill=previous_fill,
            correlation_id=str(payload.get("correlation_id") or envelope.correlation_id or ""),
            causation_id=str(payload.get("causation_id") or envelope.causation_id or ""),
            lineage_id=str(payload.get("lineage_id") or envelope.lineage_id or ""),
        )

    # ── fill tracking ───────────────────────────────────────────────

    def _track_fill(
        self, command: RecordExecutionCommand, event_id: str, envelope: EventEnvelope
    ) -> Optional[float]:
        """
        Track cumulative fill and return delta.

        Returns None for stale events (already applied).
        Raises SequenceGapError if a gap is detected.
        """
        order_id = command.order_id

        if order_id not in self._fill_states:
            self._fill_states[order_id] = FillState(
                order_id=order_id,
                instrument_id=command.instrument_id,
                ordered_quantity=command.ordered_quantity or command.fill_quantity,
            )

        state = self._fill_states[order_id]
        version = int(envelope.aggregate_version or 0)

        try:
            delta = state.record_fill(
                cumulative_fill=command.cumulative_fill,
                event_id=event_id,
                version=version,
            )
            command.previous_cumulative_fill = max(
                0, command.cumulative_fill - delta
            )
            return delta
        except StaleEventError:
            return None
        # SequenceGapError propagates up for retry

    # ── idempotency ────────────────────────────────────────────────

    def _has_execution(self, execution_id: str, event_id: str) -> bool:
        """Check if this execution has already been processed."""
        if execution_id in self._processed_executions:
            return True
        if self._check_idempotency(event_id):
            return False  # Not duplicate, proceed
        return True

    def _mark_execution(self, execution_id: str) -> None:
        """Mark an execution as processed."""
        self._processed_executions.add(execution_id)

    # ── accounting state ───────────────────────────────────────────

    def _get_accounting_state(
        self, account_id: str, currency: str
    ) -> AccountingState:
        """Get or create accounting state for an account/currency pair."""
        key = f"{account_id}:{currency}"
        if key not in self._accounting_states:
            self._accounting_states[key] = AccountingState.empty(account_id, currency)
        return self._accounting_states[key]

    def _apply_batch(
        self,
        batch: AccountingBatch,
        command: RecordExecutionCommand,
        event_id: str,
    ) -> None:
        """Apply an accounting batch to the accounting state and emit events."""
        state = self._get_accounting_state(command.account_id, command.currency)

        for entry in batch.entries:
            # Idempotency: skip already-processed (execution_id, entry_type) pairs
            if state.has_execution(entry.execution_id, entry.entry_type):
                continue

            # Emit LEDGER_ENTRY_CREATED event
            ledger_event = LedgerEntryCreatedEvent(
                entry_id=entry.entry_id,
                account_id=entry.account_id,
                currency=entry.currency,
                entry_type=entry.entry_type,
                debit=entry.debit,
                credit=entry.credit,
                amount=entry.amount,
                instrument_id=entry.instrument_id,
                order_id=entry.order_id,
                execution_id=entry.execution_id,
                source_event_id=entry.source_event_id,
                correlation_id=entry.correlation_id,
                causation_id=entry.causation_id,
                lineage_id=entry.lineage_id,
                batch_id=batch.batch_id,
                version=state.version + 1,
            )

            # Apply to state
            state.apply_event(ledger_event)
            state.record_execution(entry.execution_id, entry.entry_type)

            # Log event
            self._ledger_events.append(ledger_event)

    # ── event access ───────────────────────────────────────────────

    @property
    def ledger_events(self) -> List[LedgerEvent]:
        """All ledger events emitted by this consumer."""
        return list(self._ledger_events)

    def get_ledger_events_by_type(self, event_type: str) -> List[LedgerEvent]:
        """Filter ledger events by event_type."""
        return [e for e in self._ledger_events if e.event_type == event_type]

    def get_accounting_state(
        self, account_id: str, currency: str = "USD"
    ) -> Optional[AccountingState]:
        """Get accounting state for an account/currency pair."""
        return self._accounting_states.get(f"{account_id}:{currency}")

    def get_balance(self, account_id: str, currency: str = "USD") -> float:
        """Get current balance for an account/currency pair."""
        state = self.get_accounting_state(account_id, currency)
        if state is None:
            return 0.0
        return state.balance

    def get_fill_state(self, order_id: str) -> Optional[FillState]:
        """Get fill tracking state for an order."""
        return self._fill_states.get(order_id)
