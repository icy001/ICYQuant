"""
Execution Event Consumer — Position Service

Listens to ORDER_PARTIAL_FILL and ORDER_FILLED events,
translates them into ApplyExecutionCommands, and applies
them to the Position aggregate.

Key features:
- Fill delta calculation (prevents double-counting across partial fills)
- Execution state tracking per order
- Idempotency via event_id and execution_id
- Sequence gap detection via aggregate_version
- Over-fill / negative-delta protection
- Consumer isolation (independent offset, retry, dead-letter)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from services.integration.event_consumer import (
    DeliveryState,
    EventConsumer,
    EventSequenceGap,
)
from services.integration.event_envelope import EventEnvelope
from services.integration.event_registry import EventRegistry

from ..commands.apply_execution import ApplyExecutionCommand
from ..domain.position import (
    Position,
    PositionOverFillError,
    PositionSide,
    PositionSnapshot,
)
from ..domain.position_event import PositionEvent
from ..exceptions.duplicate_execution import DuplicateExecutionError
from ..exceptions.position_conflict import PositionConflictError
from ..exceptions.position_error import (
    InvalidExecutionError,
    OverFillError,
    SequenceGapError,
    StaleEventError,
)

# ------------------------------------------------------------------
#  Supported event types
# ------------------------------------------------------------------

SUPPORTED_EVENT_TYPES = {"ORDER_PARTIAL_FILL", "ORDER_FILLED"}


# ------------------------------------------------------------------
#  Execution state per order
# ------------------------------------------------------------------

@dataclass
class ExecutionState:
    """Tracks per-order execution progress for fill-delta calculation."""

    order_id: str
    instrument_id: str
    ordered_quantity: float
    filled_quantity: float = 0.0  # cumulative fill applied so far

    last_execution_event_id: str = ""
    last_event_version: int = 0

    def record_fill(self, cumulative_fill: float, event_id: str, version: int) -> float:
        """
        Record new cumulative fill and return the delta.

        Raises SequenceGapError if version has a gap.
        """
        if self.last_event_version > 0 and version > self.last_event_version + 1:
            raise SequenceGapError(
                f"Event sequence gap for order {self.order_id}: "
                f"expected version {self.last_event_version + 1}, "
                f"got version {version}"
            )

        if version <= self.last_event_version and self.last_event_version > 0:
            raise StaleEventError(
                f"Stale event for order {self.order_id}: "
                f"version {version} <= last {self.last_event_version}"
            )

        delta = cumulative_fill - self.filled_quantity
        self.filled_quantity = cumulative_fill
        self.last_execution_event_id = event_id
        self.last_event_version = version
        return delta


# ------------------------------------------------------------------
#  Consumer
# ------------------------------------------------------------------

class ExecutionEventConsumer(EventConsumer):
    """
    Position Service consumer for execution events.

    Pipeline:
        Event → Validate → Deduplicate → Translate → Apply → Persist

    Does NOT commit offset until position update is persisted.
    """

    def __init__(self, registry: Optional[EventRegistry] = None):
        super().__init__(registry, consumer_group="position-service")

        # ── per-order execution state ──────────────────────────
        self._execution_states: dict[str, ExecutionState] = {}
        self._execution_state_by_key: dict[str, ExecutionState] = {}

        # ── idempotency: duplicate execution tracking ──────────
        self._processed_executions: set[str] = set()

        # ── in-memory store (instance-level, not class-level) ──
        self._positions: dict[str, PositionSnapshot] = {}

        # ── position event log ─────────────────────────────────
        self._position_events: list[PositionEvent] = []

    # ------------------------------------------------------------------
    #  Execution state helpers
    # ------------------------------------------------------------------

    def ensure_execution_state(
        self,
        order_id: str,
        instrument_id: str,
        ordered_quantity: float,
    ) -> ExecutionState:
        """Get or create execution state for an order."""
        if order_id not in self._execution_states:
            self._execution_states[order_id] = ExecutionState(
                order_id=order_id,
                instrument_id=instrument_id,
                ordered_quantity=ordered_quantity,
            )
        return self._execution_states[order_id]

    def _check_execution_duplicate(self, execution_id: str, event_id: str) -> bool:
        """Returns True if this execution was already processed."""
        if execution_id in self._processed_executions:
            return True
        return False

    def _mark_execution_processed(self, execution_id: str, event_id: str) -> None:
        """Mark execution as processed for idempotency."""
        self._processed_executions.add(execution_id)
        self._processed_events.add(event_id)

    # ------------------------------------------------------------------
    #  Event handling
    # ------------------------------------------------------------------

    def on_envelope(self, envelope: EventEnvelope) -> None:
        """Main entry point — called by event bus on each received event."""
        event_type = envelope.event_type
        event_id = envelope.event_id

        # ── filter: only process supported event types ─────────
        if event_type not in SUPPORTED_EVENT_TYPES:
            self._mark_delivered(event_id)
            return

        # ── idempotency: duplicate event ───────────────────────
        if not self._check_idempotency(event_id):
            return

        try:
            # 1.  Basic envelope check
            if not envelope.event_id or not envelope.aggregate_id:
                raise InvalidExecutionError("envelope missing event_id or aggregate_id")

            # 2.  Determine if BUY or SELL
            side = self._extract_side(envelope)
            if side is None:
                self._delivery_state[event_id] = DeliveryState.FAILED
                self._mark_processed(event_id)
                return

            # 3.  Build command
            command = self._build_command(envelope, side)

            # 4.  Validate command
            command.validate()

            # 5.  Check execution duplicate
            if self._check_execution_duplicate(command.execution_id, event_id):
                self._mark_delivered(event_id)
                return

            # 6.  Update execution state & compute delta
            order_id = command.order_id
            state = self.ensure_execution_state(
                order_id=order_id,
                instrument_id=command.instrument_id,
                ordered_quantity=command.ordered_quantity or command.fill_quantity,
            )

            try:
                delta = state.record_fill(
                    cumulative_fill=command.cumulative_fill,
                    event_id=event_id,
                    version=command.aggregate_version,
                )
            except SequenceGapError:
                self._delivery_state[event_id] = DeliveryState.PENDING
                raise
            except StaleEventError:
                self._mark_delivered(event_id)
                return

            # 7.  Validate delta
            command._delta = delta
            command.ensure_valid_delta()

            if not command.is_effective:
                self._mark_delivered(event_id)
                return

            # 8.  Apply to position aggregate
            self._apply_command(command, event_id)

            # 9.  Mark success
            self._mark_execution_processed(command.execution_id, event_id)
            self._mark_delivered(event_id)

        except (
            InvalidExecutionError,
            OverFillError,
            PositionOverFillError,
            PositionConflictError,
            DuplicateExecutionError,
        ) as exc:
            self._handle_failure(envelope, exc)

    # ------------------------------------------------------------------
    #  Internal builders
    # ------------------------------------------------------------------

    def _extract_side(self, envelope: EventEnvelope) -> Optional[str]:
        """Extract BUY/SELL side from envelope payload."""
        payload = envelope.payload
        if isinstance(payload, dict):
            side = payload.get("side", "").upper()
            if side in ("BUY", "SELL"):
                return side
            # Fallback: try direction
            direction = payload.get("direction", "").upper()
            if direction in ("BUY", "SELL"):
                return direction
        return None

    def _build_command(
        self, envelope: EventEnvelope, side: str
    ) -> ApplyExecutionCommand:
        """Build ApplyExecutionCommand from event envelope."""
        payload = envelope.payload if isinstance(envelope.payload, dict) else {}

        quantity = float(payload.get("quantity", payload.get("filled_quantity", 0)))
        price = float(payload.get("price", payload.get("average_price", 0)))
        cumulative_fill = float(
            payload.get("cumulative_fill", payload.get("filled_quantity", quantity))
        )
        previous_fill = float(payload.get("previous_fill", 0.0))

        ordered_qty = float(
            payload.get("ordered_quantity", payload.get("order_quantity", quantity))
        )

        return ApplyExecutionCommand(
            account_id=payload.get("account_id", envelope.aggregate_id),
            instrument_id=payload.get("instrument_id", payload.get("symbol", "")),
            side=side,
            fill_quantity=quantity,
            fill_price=price,
            order_id=envelope.aggregate_id,
            execution_id=payload.get("execution_id", f"EXEC-{envelope.event_id}"),
            ordered_quantity=ordered_qty,
            cumulative_fill=cumulative_fill,
            previous_cumulative_fill=previous_fill,
            source_event_id=envelope.event_id,
            source_event_type=envelope.event_type,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.causation_id,
            lineage_id=envelope.lineage_id,
            aggregate_version=envelope.aggregate_version,
        )

    def _apply_command(self, command: ApplyExecutionCommand, event_id: str) -> None:
        """
        Apply command to position aggregate.

        In production this would:
        1. Load Position from repository
        2. Call position.apply_fill() or position.apply_reduction()
        3. Collect and persist position events
        4. Update projection

        The current in-memory implementation demonstrates the pipeline.
        """
        # ── Load or create position ────────────────────────────
        position_id = f"POS-{command.account_id}-{command.instrument_id}"
        position = self._load_or_create_position(
            position_id=position_id,
            account_id=command.account_id,
            instrument_id=command.instrument_id,
            side=command.position_side,
        )

        # ── Apply fill ─────────────────────────────────────────
        try:
            if command.is_buy:
                event = position.apply_fill(
                    fill_quantity=command.delta,
                    fill_price=command.fill_price,
                    execution_id=command.execution_id,
                    order_id=command.order_id,
                    source_event_id=command.source_event_id,
                    correlation_id=command.correlation_id,
                    causation_id=command.causation_id,
                    lineage_id=command.lineage_id,
                )
            else:
                # SELL: check for reversal first
                if position.detect_reversal(
                    reduction_quantity=command.delta,
                    order_id=command.order_id,
                ):
                    raise PositionOverFillError(
                        f"Position reversal detected: cannot reduce {command.delta} "
                        f"when position is {position.quantity}. "
                        f"Reversal requires dedicated close + open flow."
                    )
                event = position.apply_reduction(
                    reduction_quantity=command.delta,
                    fill_price=command.fill_price,
                    execution_id=command.execution_id,
                    order_id=command.order_id,
                    source_event_id=command.source_event_id,
                    correlation_id=command.correlation_id,
                    causation_id=command.causation_id,
                    lineage_id=command.lineage_id,
                )
        except PositionOverFillError:
            raise

        # ── Collect events ─────────────────────────────────────
        if event is not None:
            self._on_position_event(position, event)

        # ── Persist position snapshot (in-memory for now) ──────
        self._positions[position_id] = position.snapshot()

    # ------------------------------------------------------------------
    #  In-memory position store (production: use repository)
    # ------------------------------------------------------------------

    def _load_or_create_position(
        self,
        position_id: str,
        account_id: str,
        instrument_id: str,
        side: str,
    ) -> Position:
        """Load existing position or create new one."""
        snapshot = self._positions.get(position_id)
        if snapshot is not None:
            return Position(
                position_id=snapshot.position_id,
                account_id=snapshot.account_id,
                instrument_id=snapshot.instrument_id,
                side=PositionSide(snapshot.side),
                quantity=snapshot.quantity,
                average_price=snapshot.average_price,
                realized_pnl=snapshot.realized_pnl,
                version=snapshot.version,
                last_execution_id=snapshot.last_execution_id,
                last_order_id=snapshot.last_order_id,
            )

        side_enum = PositionSide.LONG if side == "LONG" else PositionSide.SHORT
        return Position.open_long(
            position_id=position_id,
            account_id=account_id,
            instrument_id=instrument_id,
        ) if side_enum == PositionSide.LONG else Position.open_short(
            position_id=position_id,
            account_id=account_id,
            instrument_id=instrument_id,
        )

    # ── Abstract method required by EventConsumer base ─────────
    def handle(self, envelope: EventEnvelope) -> None:
        """Delegate to on_envelope for custom pipeline processing."""
        self.on_envelope(envelope)

    # ── Position event callback (override for projection) ──────

    def _on_position_event(self, position: Position, event: PositionEvent) -> None:
        """Called when a position domain event is generated."""
        self._position_events.append(event)

    # ------------------------------------------------------------------
    #  Query helpers
    # ------------------------------------------------------------------

    def get_execution_state(self, order_id: str) -> Optional[ExecutionState]:
        """Get execution state for an order."""
        return self._execution_states.get(order_id)

    def get_position_snapshot(self, position_id: str) -> Optional[PositionSnapshot]:
        """Get current position snapshot."""
        return self._positions.get(position_id)

    def get_position_events(self) -> list[PositionEvent]:
        """Get all generated position events (for testing)."""
        return list(self._position_events)

    def get_consumer_group(self) -> str:
        return self._consumer_group
