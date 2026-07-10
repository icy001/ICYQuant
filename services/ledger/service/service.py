from datetime import datetime
from typing import List, Optional
from uuid import UUID

from services.contracts.dto import TradeDTO

from ..event import LedgerEvent
from ..event_type import LedgerEventType
from ..exceptions import EventValidationError
from ..repository import EventRepository


class LedgerService:
    def __init__(self, event_repository: EventRepository) -> None:
        self._event_repository = event_repository

    def record_event(self, event: LedgerEvent) -> None:
        self._validate_event(event)
        self._event_repository.save(event)

    def record_deposit(self, user_id: str, amount: float) -> LedgerEvent:
        event = LedgerEvent(
            event_type=LedgerEventType.CASH_DEPOSITED,
            aggregate_id=user_id,
            payload={
                "user_id": user_id,
                "amount": amount,
                "currency": "USD",
            },
        )
        self.record_event(event)
        return event

    def record_withdrawal(self, user_id: str, amount: float) -> LedgerEvent:
        event = LedgerEvent(
            event_type=LedgerEventType.CASH_WITHDRAWN,
            aggregate_id=user_id,
            payload={
                "user_id": user_id,
                "amount": amount,
                "currency": "USD",
            },
        )
        self.record_event(event)
        return event

    def record_order_created(self, user_id: str, order_id: str, symbol: str, side: str, quantity: float) -> LedgerEvent:
        event = LedgerEvent(
            event_type=LedgerEventType.ORDER_CREATED,
            aggregate_id=user_id,
            payload={
                "user_id": user_id,
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
            },
        )
        self.record_event(event)
        return event

    def record_order_filled(self, user_id: str, order_id: str, symbol: str, side: str, quantity: float, price: float) -> LedgerEvent:
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
        self.record_event(event)
        return event

    def record_commission(self, user_id: str, amount: float, reference_id: str) -> LedgerEvent:
        event = LedgerEvent(
            event_type=LedgerEventType.COMMISSION_CHARGED,
            aggregate_id=user_id,
            payload={
                "user_id": user_id,
                "amount": amount,
                "reference_id": reference_id,
            },
        )
        self.record_event(event)
        return event

    def get_events(self, user_id: str) -> List[LedgerEvent]:
        return self._event_repository.get_by_stream(user_id)

    def get_event(self, event_id: UUID) -> Optional[LedgerEvent]:
        return self._event_repository.get_by_id(event_id)

    def get_all_events(self) -> List[LedgerEvent]:
        return self._event_repository.get_all()

    def replay(self) -> List[LedgerEvent]:
        return self._event_repository.replay()

    def _validate_event(self, event: LedgerEvent) -> None:
        if not event.event_type:
            raise EventValidationError("Event type is required")