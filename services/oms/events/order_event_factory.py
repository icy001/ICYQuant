"""OrderEventFactory — creates typed events with correct payloads."""
from __future__ import annotations

from typing import Any, Dict, Optional

from .order_event import OrderEvent
from .order_event_type import OrderEventType
from .order_event_metadata import OrderEventMetadata


class OrderEventFactory:
    """Factory for creating order events with proper payloads.

    Each factory method constructs an OrderEvent with the correct
    event type and a well-structured payload.
    """

    @staticmethod
    def accepted(order_id: str, sequence: int,
                 lineage_id: str = "",
                 flow_id: str = "",
                 certificate_id: str = "",
                 metadata: Optional[OrderEventMetadata] = None,
                 previous_hash: str = "") -> OrderEvent:
        return OrderEvent.create(
            order_id=order_id,
            event_type=OrderEventType.ORDER_ACCEPTED,
            sequence=sequence,
            lineage_id=lineage_id,
            flow_id=flow_id,
            certificate_id=certificate_id,
            payload={"certificate_id": certificate_id},
            metadata=metadata or OrderEventMetadata.for_system(),
            previous_event_hash=previous_hash,
        ).seal()

    @staticmethod
    def created(order_id: str, sequence: int,
                symbol: str, side: str, order_type: str,
                quantity: float, price: float = 0,
                lineage_id: str = "",
                flow_id: str = "",
                certificate_id: str = "",
                metadata: Optional[OrderEventMetadata] = None,
                previous_hash: str = "") -> OrderEvent:
        return OrderEvent.create(
            order_id=order_id,
            event_type=OrderEventType.ORDER_CREATED,
            sequence=sequence,
            lineage_id=lineage_id,
            flow_id=flow_id,
            certificate_id=certificate_id,
            payload={
                "symbol": symbol, "side": side,
                "order_type": order_type,
                "quantity": quantity, "price": price,
            },
            metadata=metadata or OrderEventMetadata.for_system(),
            previous_event_hash=previous_hash,
        ).seal()

    @staticmethod
    def routing_started(order_id: str, sequence: int,
                        route: str = "",
                        lineage_id: str = "",
                        flow_id: str = "",
                        certificate_id: str = "",
                        metadata: Optional[OrderEventMetadata] = None,
                        previous_hash: str = "") -> OrderEvent:
        return OrderEvent.create(
            order_id=order_id,
            event_type=OrderEventType.ORDER_ROUTING_STARTED,
            sequence=sequence,
            lineage_id=lineage_id,
            flow_id=flow_id,
            certificate_id=certificate_id,
            payload={"route": route},
            metadata=metadata or OrderEventMetadata.for_system(),
            previous_event_hash=previous_hash,
        ).seal()

    @staticmethod
    def working(order_id: str, sequence: int,
                venue: str = "",
                lineage_id: str = "",
                flow_id: str = "",
                certificate_id: str = "",
                metadata: Optional[OrderEventMetadata] = None,
                previous_hash: str = "") -> OrderEvent:
        return OrderEvent.create(
            order_id=order_id,
            event_type=OrderEventType.ORDER_WORKING,
            sequence=sequence,
            lineage_id=lineage_id,
            flow_id=flow_id,
            certificate_id=certificate_id,
            payload={"venue": venue},
            metadata=metadata or OrderEventMetadata.for_system(),
            previous_event_hash=previous_hash,
        ).seal()

    @staticmethod
    def partial_fill(order_id: str, sequence: int,
                     fill_quantity: float,
                     fill_price: float,
                     execution_id: str = "",
                     lineage_id: str = "",
                     flow_id: str = "",
                     certificate_id: str = "",
                     metadata: Optional[OrderEventMetadata] = None,
                     previous_hash: str = "") -> OrderEvent:
        return OrderEvent.create(
            order_id=order_id,
            event_type=OrderEventType.ORDER_PARTIAL_FILL,
            sequence=sequence,
            lineage_id=lineage_id,
            flow_id=flow_id,
            certificate_id=certificate_id,
            payload={
                "fill_quantity": fill_quantity,
                "fill_price": fill_price,
                "execution_id": execution_id,
            },
            metadata=metadata or OrderEventMetadata.for_execution(execution_id),
            previous_event_hash=previous_hash,
        ).seal()

    @staticmethod
    def filled(order_id: str, sequence: int,
               fill_quantity: float,
               fill_price: float,
               execution_id: str = "",
               lineage_id: str = "",
               flow_id: str = "",
               certificate_id: str = "",
               metadata: Optional[OrderEventMetadata] = None,
               previous_hash: str = "") -> OrderEvent:
        return OrderEvent.create(
            order_id=order_id,
            event_type=OrderEventType.ORDER_FILLED,
            sequence=sequence,
            lineage_id=lineage_id,
            flow_id=flow_id,
            certificate_id=certificate_id,
            payload={
                "fill_quantity": fill_quantity,
                "fill_price": fill_price,
                "execution_id": execution_id,
            },
            metadata=metadata or OrderEventMetadata.for_execution(execution_id),
            previous_event_hash=previous_hash,
        ).seal()

    @staticmethod
    def cancel_requested(order_id: str, sequence: int,
                         reason: str = "",
                         lineage_id: str = "",
                         flow_id: str = "",
                         certificate_id: str = "",
                         metadata: Optional[OrderEventMetadata] = None,
                         previous_hash: str = "") -> OrderEvent:
        return OrderEvent.create(
            order_id=order_id,
            event_type=OrderEventType.ORDER_CANCEL_REQUESTED,
            sequence=sequence,
            lineage_id=lineage_id,
            flow_id=flow_id,
            certificate_id=certificate_id,
            payload={"reason": reason},
            metadata=metadata or OrderEventMetadata.for_system(),
            previous_event_hash=previous_hash,
        ).seal()

    @staticmethod
    def cancelled(order_id: str, sequence: int,
                  cancelled_quantity: float = 0,
                  reason: str = "",
                  lineage_id: str = "",
                  flow_id: str = "",
                  certificate_id: str = "",
                  metadata: Optional[OrderEventMetadata] = None,
                  previous_hash: str = "") -> OrderEvent:
        return OrderEvent.create(
            order_id=order_id,
            event_type=OrderEventType.ORDER_CANCELLED,
            sequence=sequence,
            lineage_id=lineage_id,
            flow_id=flow_id,
            certificate_id=certificate_id,
            payload={
                "cancelled_quantity": cancelled_quantity,
                "reason": reason,
            },
            metadata=metadata or OrderEventMetadata.for_system(),
            previous_event_hash=previous_hash,
        ).seal()

    @staticmethod
    def rejected(order_id: str, sequence: int,
                 reason: str = "",
                 lineage_id: str = "",
                 flow_id: str = "",
                 certificate_id: str = "",
                 metadata: Optional[OrderEventMetadata] = None,
                 previous_hash: str = "") -> OrderEvent:
        return OrderEvent.create(
            order_id=order_id,
            event_type=OrderEventType.ORDER_REJECTED,
            sequence=sequence,
            lineage_id=lineage_id,
            flow_id=flow_id,
            certificate_id=certificate_id,
            payload={"reason": reason},
            metadata=metadata or OrderEventMetadata.for_system(),
            previous_event_hash=previous_hash,
        ).seal()

    @staticmethod
    def expired(order_id: str, sequence: int,
                lineage_id: str = "",
                flow_id: str = "",
                certificate_id: str = "",
                metadata: Optional[OrderEventMetadata] = None,
                previous_hash: str = "") -> OrderEvent:
        return OrderEvent.create(
            order_id=order_id,
            event_type=OrderEventType.ORDER_EXPIRED,
            sequence=sequence,
            lineage_id=lineage_id,
            flow_id=flow_id,
            certificate_id=certificate_id,
            payload={},
            metadata=metadata or OrderEventMetadata.for_system(),
            previous_event_hash=previous_hash,
        ).seal()

    @staticmethod
    def failed(order_id: str, sequence: int,
               reason: str = "",
               lineage_id: str = "",
               flow_id: str = "",
               certificate_id: str = "",
               metadata: Optional[OrderEventMetadata] = None,
               previous_hash: str = "") -> OrderEvent:
        return OrderEvent.create(
            order_id=order_id,
            event_type=OrderEventType.ORDER_FAILED,
            sequence=sequence,
            lineage_id=lineage_id,
            flow_id=flow_id,
            certificate_id=certificate_id,
            payload={"reason": reason},
            metadata=metadata or OrderEventMetadata.for_system(),
            previous_event_hash=previous_hash,
        ).seal()

    @staticmethod
    def amended(order_id: str, sequence: int,
                new_quantity: float = 0,
                new_price: float = 0,
                lineage_id: str = "",
                flow_id: str = "",
                certificate_id: str = "",
                metadata: Optional[OrderEventMetadata] = None,
                previous_hash: str = "") -> OrderEvent:
        return OrderEvent.create(
            order_id=order_id,
            event_type=OrderEventType.ORDER_AMENDED,
            sequence=sequence,
            lineage_id=lineage_id,
            flow_id=flow_id,
            certificate_id=certificate_id,
            payload={
                "new_quantity": new_quantity,
                "new_price": new_price,
            },
            metadata=metadata or OrderEventMetadata.for_system(),
            previous_event_hash=previous_hash,
        ).seal()
