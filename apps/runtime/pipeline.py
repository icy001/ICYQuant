"""Trading pipeline runtime - wires official engines into a full chain.

Pipeline: Signal -> Risk -> Order -> Execution -> Position -> Ledger
          \\__________________ Reconciliation __________________/

Feature Freeze: only wires existing official engines; no new engine logic.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from services.common.event_bus import EventBus
from services.contracts.events import Event, EventType
from services.oms.order.manager import OrderManager
from services.risk.service.risk_engine import RiskEngine
from services.position.manager import PositionManager
from services.position.model import Position
from services.position.repository import PositionRepository
from services.position.service import PositionService
from services.ledger.memory_store import MemoryEventStore
from services.ledger.repository.event_repository import EventRepository
from services.ledger.service import LedgerService
from services.reconciliation.engine import ReconciliationEngine

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Signal:
    """User-constructed trading signal (fixed scenario input)."""

    signal_id: str = field(default_factory=lambda: f"sig_{uuid4().hex[:8]}")
    symbol: str = "AAPL"
    side: str = "BUY"
    quantity: int = 100
    price: Optional[Decimal] = None
    strategy_id: str = "SCENARIO"

    def to_event(self) -> Event:
        return Event(
            event_id=f"evt_{uuid4().hex[:8]}",
            event_type=EventType.ORDER_CREATED,
            order_id=self.signal_id,
            timestamp=utcnow(),
            payload={
                "symbol": self.symbol,
                "side": self.side,
                "quantity": self.quantity,
                "strategy_id": self.strategy_id,
                "price": str(self.price) if self.price else None,
            },
        )


@dataclass
class PipelineResult:
    """Result of processing one signal through the pipeline."""

    signal: Signal
    order_id: Optional[str] = None
    order_status: Optional[str] = None
    risk_decision: Optional[dict] = None
    filled_quantity: int = 0
    execution_reason: Optional[str] = None
    positions: dict = field(default_factory=dict)
    ledger: dict = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)


class TradingPipeline:
    """Runs a Signal through the full official engine chain.

    Uses the official in-memory EventBus so that all engines
    (Risk, Order, Position, Ledger, Reconciliation) communicate
    exactly as they do in production.
    """

    def __init__(self) -> None:
        self.bus = EventBus()
        self.order_manager = OrderManager()
        self.risk_engine = RiskEngine(self.bus)
        self.position_repo = PositionRepository()
        self.position_manager = PositionManager(self.position_repo)
        self.position_service = PositionService(self.position_manager)
        self.ledger_store = MemoryEventStore()
        self.ledger_service = LedgerService(EventRepository(self.ledger_store))
        self.reconciliation = ReconciliationEngine()

        self._events: list[Event] = []
        self._applied: set[tuple] = set()  # dedupe: (order_id, qty, price)
        self._wiring_done = False
        self._ledger_snapshot: dict = {"events": [], "count": 0}

    # ------------------------------------------------------------------
    # Event wiring: connect official engines to the bus
    # ------------------------------------------------------------------
    def wire(self) -> "TradingPipeline":
        if self._wiring_done:
            return self

        # Risk Engine subscribes to ORDER_CREATED on the bus itself
        # (official RiskEngine.__init__ registers its handlers).

        # Trace every event for assertions & replay
        for event_type in EventType:
            self.bus.subscribe(event_type, self._trace)

        self._wiring_done = True
        return self

    def _trace(self, event: Event) -> None:
        self._events.append(event)
        logger.debug("event: %s %s", event.event_type.value, event.order_id)

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------
    def submit_signal(self, signal: Signal) -> PipelineResult:
        self.wire()
        result = PipelineResult(signal=signal)
        event = signal.to_event()
        self.bus.publish(event)

        # Risk decision (approved flag lives on RISK_CHECKED payload)
        checked = self._last_payload([EventType.RISK_CHECKED], signal.signal_id)
        approved_event = self._last_payload([EventType.ORDER_APPROVED], signal.signal_id)
        rejected_event = self._last_payload([EventType.ORDER_REJECTED], signal.signal_id)
        result.risk_decision = checked or {}
        if checked is None and approved_event is None and rejected_event is None:
            result.execution_reason = "risk_no_decision"
            return result

        approved = (checked or {}).get("approved") or approved_event is not None
        if not approved:
            result.execution_reason = "risk_rejected"
            return result

        # Order: create -> validate -> route -> submit (broker ack happens on fill)
        order = self.order_manager.create_order(
            symbol=signal.symbol,
            side=signal.side,
            quantity=signal.quantity,
            strategy_id=signal.strategy_id,
        )
        self.order_manager.validate_order(order.order_id)
        self.order_manager.route_order(order.order_id)
        self.order_manager.submit_order(order.order_id)
        result.order_id = order.order_id
        result.order_status = order.status.value
        return result

    def acknowledge_order(self, result: PipelineResult) -> None:
        """Broker acknowledges receipt (SUBMITTED -> ACKNOWLEDGED)."""
        self.order_manager.acknowledge_order(result.order_id)
        result.order_status = self.order_manager.get_order(result.order_id).status.value

    def fill_order(
        self,
        result: PipelineResult,
        quantity: int,
        price: float,
        record_position: bool = True,
    ) -> None:
        """Simulated broker fill against an acknowledged order.

        Args:
            result: pipeline result carrying the order
            quantity: quantity filled in THIS execution
            price: execution price for THIS fill
            record_position: False simulates a lost Position event (Scenario 06)
        """
        if not result.order_id:
            raise ValueError("no order to fill")

        order = self.order_manager.get_order(result.order_id)
        if order.status.value in ("SUBMITTED", "ROUTED"):
            self.acknowledge_order(result)

        self.order_manager.fill_order(result.order_id, quantity, price)
        result.order_status = self.order_manager.get_order(result.order_id).status.value
        result.filled_quantity += quantity

        if record_position:
            self._apply_trade(result, order, quantity, price)
        else:
            # Position event "lost": ledger still records (Scenario 06)
            self._record_ledger(order, quantity, price)
        result.positions = dict(self.position_repo.positions)

    def reject_order(self, result: PipelineResult, reason: str = "broker_reject") -> None:
        """Simulated broker reject (from SUBMITTED)."""
        if not result.order_id:
            raise ValueError("no order to reject")
        self.order_manager.reject_order(result.order_id, reason=reason)
        result.order_status = self.order_manager.get_order(result.order_id).status.value
        result.execution_reason = reason

    def _apply_trade(self, result: PipelineResult, order, quantity: int, price: float) -> None:
        """Apply an executed order to Position and Ledger (official engines).

        Idempotent: the same (order_id, quantity, price) execution delivered
        twice is ignored (Scenario 05 duplicate-event protection).
        """
        key = (order.order_id, quantity, price)
        if key in self._applied:
            return  # duplicate delivery
        self._applied.add(key)

        # Position: aggregate per symbol
        existing = self.position_repo.find(order.symbol)
        if existing:
            new_qty = existing.quantity + quantity
            existing.avg_price = (
                existing.avg_price * existing.quantity + price * quantity
            ) / new_qty
            existing.quantity = new_qty
            self.position_repo.save(existing)
        else:
            position = Position(
                position_id=order.symbol,
                account_id=order.strategy_id or "SYSTEM",
                portfolio_id="SCENARIO",
                symbol=order.symbol,
                quantity=quantity,
                avg_price=float(price),
                side=order.side,
            )
            self.position_service.create_position(position)

        self._record_ledger(order, quantity, price)
        result.positions = dict(self.position_repo.positions)

    def _record_ledger(self, order, quantity: int, price: float) -> None:
        self.ledger_service.record_order_filled(
            user_id=order.strategy_id or "SYSTEM",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=quantity,
            price=price,
        )
        result_ledger = {
            "events": [e.to_dict() for e in self.ledger_store.all_events()],
            "count": self.ledger_store.count(),
        }
        self._ledger_snapshot = result_ledger

    @property
    def ledger(self) -> dict:
        return self._ledger_snapshot

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------
    def reconcile(self, result: PipelineResult) -> dict:
        """Compare internal position vs ledger expectation."""
        positions = dict(self.position_repo.positions)
        actual = sum(p.quantity for p in positions.values())
        ledger_events = list(self.ledger_store.all_events())
        ledger_qty = sum(
            float(e.payload.get("quantity", 0))
            for e in ledger_events
            if getattr(e, "payload", {}) and e.payload.get("quantity")
        )
        if not positions and ledger_qty == 0:
            return {"status": "OK", "detail": "no positions"}
        return {
            "status": "OK" if actual == ledger_qty else "MISMATCH",
            "position": actual,
            "ledger": ledger_qty,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _last_payload(self, event_types: list[EventType], order_id: str) -> Optional[dict]:
        for event in reversed(self._events):
            if event.event_type in event_types and event.order_id == order_id:
                return event.payload
        return None

    def events_for(self, event_type: EventType, order_id: Optional[str] = None) -> list[Event]:
        return [
            e
            for e in self._events
            if e.event_type == event_type and (order_id is None or e.order_id == order_id)
        ]
