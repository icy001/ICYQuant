from typing import List, Optional

from .event import LedgerEvent
from .event_type import LedgerEventType
from .exceptions import EventValidationError
from .projector import Projection
from .repository import EventRepository
from .store import EventStore, InMemoryEventStore, SQLiteEventStore


class Ledger:
    def __init__(self, event_store: Optional[EventStore] = None):
        self.store: EventStore = event_store or InMemoryEventStore()
        self._repository = EventRepository(self.store)
        self.projectors: List[Projection] = []

    def register_projector(self, projector: Projection) -> None:
        self.projectors.append(projector)

    def record(self, event: LedgerEvent) -> None:
        self.store.append(event)
        for projector in self.projectors:
            projector.apply(event)

    def record_deposit(self, user_id: str, amount: float) -> LedgerEvent:
        event = LedgerEvent(
            event_type=LedgerEventType.CASH_DEPOSITED,
            aggregate_id=user_id,
            payload={"user_id": user_id, "amount": amount},
        )
        self.record(event)
        return event

    def record_withdrawal(self, user_id: str, amount: float) -> LedgerEvent:
        event = LedgerEvent(
            event_type=LedgerEventType.CASH_WITHDRAWN,
            aggregate_id=user_id,
            payload={"user_id": user_id, "amount": amount},
        )
        self.record(event)
        return event

    def record_order_filled(
        self, user_id: str, order_id: str, symbol: str, side: str, quantity: float, price: float
    ) -> LedgerEvent:
        cash_change = -quantity * price if side == "BUY" else quantity * price
        event = LedgerEvent(
            event_type=LedgerEventType.ORDER_FILLED,
            aggregate_id=user_id,
            payload={
                "user_id": user_id,
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
                "cash_change": cash_change,
            },
        )
        self.record(event)
        return event

    def replay(self) -> List[LedgerEvent]:
        for projector in self.projectors:
            projector.reset()

        events = self.store.all_events()
        for event in events:
            for projector in self.projectors:
                projector.apply(event)

        return events

    def snapshot(self) -> dict:
        snapshot = {}
        for projector in self.projectors:
            if hasattr(projector, "state"):
                snapshot[type(projector).__name__] = projector.state
        return snapshot

    def restore(self, snapshot: dict) -> None:
        for projector in self.projectors:
            name = type(projector).__name__
            if name in snapshot:
                projector.state = snapshot[name]

    def get_events(self, stream_id: str = "default") -> List[LedgerEvent]:
        return self._repository.get_by_stream(stream_id)