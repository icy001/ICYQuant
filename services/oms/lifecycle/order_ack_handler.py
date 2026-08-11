"""Order ACK Handler — Handles broker acknowledgment events.

Processes ACK (acknowledgment) messages from broker gateways,
confirming that the exchange has received the order.

Pipeline:
    Exchange ACK → Duplicate Check → Sequence Check → Transition to ACKNOWLEDGED
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from services.oms.order.models import Order, OrderStatus
from services.oms.lifecycle.state_transition_validator import LifecycleStatus
from services.oms.lifecycle.transition_engine import (
    TransitionEngine,
    TransitionEvent,
    TransitionEventType,
    TransitionResult,
)
from services.oms.lifecycle.duplicate_event_detector import DuplicateEventDetector
from services.oms.lifecycle.event_sequence_checker import EventSequenceChecker

logger = logging.getLogger(__name__)


@dataclass
class AckResult:
    """Result of ACK processing."""
    order_id: str
    accepted: bool = False
    broker_order_id: str = ""
    exchange_order_id: str = ""
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    transition: Optional[TransitionResult] = None

    @property
    def success(self) -> bool:
        return self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "accepted": self.accepted,
            "broker_order_id": self.broker_order_id,
            "exchange_order_id": self.exchange_order_id,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


class OrderAckHandler:
    """Handles broker acknowledgment events.

    Processes ACK messages from broker gateways, performing duplicate
    detection and sequence validation before transitioning the order
    to ACKNOWLEDGED state.

    Usage::

        handler = OrderAckHandler(transition_engine, duplicate_detector, sequence_checker)
        result = await handler.handle_ack(order, broker_order_id="BKR-001")
    """

    def __init__(
        self,
        transition_engine: TransitionEngine,
        duplicate_detector: DuplicateEventDetector,
        sequence_checker: EventSequenceChecker,
    ) -> None:
        self._engine = transition_engine
        self._duplicate = duplicate_detector
        self._sequence = sequence_checker

    async def handle_ack(
        self,
        order: Order,
        broker_order_id: str = "",
        exchange_order_id: str = "",
        ack_event_id: Optional[str] = None,
        sequence_id: int = 0,
        payload: Optional[dict[str, Any]] = None,
    ) -> AckResult:
        """Process a broker ACK event.

        Args:
            order: Order to acknowledge
            broker_order_id: Broker-assigned order ID
            exchange_order_id: Exchange-assigned order ID
            ack_event_id: Unique event ID for deduplication
            sequence_id: Sequence number for ordering
            payload: Additional ACK data

        Returns:
            AckResult with acceptance status
        """
        event_id = ack_event_id or f"ack-{order.order_id}"

        # Duplicate check
        dup = self._duplicate.check(event_id, order.order_id)
        if dup.is_duplicate:
            logger.warning(f"Duplicate ACK for order {order.order_id}: {event_id}")
            return AckResult(
                order_id=order.order_id,
                reason=f"Duplicate ACK: {event_id}",
            )

        # Sequence check
        if sequence_id > 0:
            seq = self._sequence.check(order.order_id, sequence_id)
            if seq.status.value == "gap_detected":
                logger.warning(
                    f"Sequence gap in ACK for order {order.order_id}: "
                    f"missing {seq.missing_sequences}"
                )

        # Execute transition
        event = TransitionEvent(
            event_id=event_id,
            order_id=order.order_id,
            event_type=TransitionEventType.ACKNOWLEDGE,
            from_status=LifecycleStatus(order.status.value),
            to_status=LifecycleStatus.ACKNOWLEDGED,
            payload=payload or {
                "broker_order_id": broker_order_id,
                "exchange_order_id": exchange_order_id,
            },
        )

        result = await self._engine.transition(order, event)

        logger.info(
            f"Order {order.order_id} ACK processed: "
            f"broker_order_id={broker_order_id}, "
            f"exchange_order_id={exchange_order_id}"
        )

        return AckResult(
            order_id=order.order_id,
            accepted=result.success,
            broker_order_id=broker_order_id,
            exchange_order_id=exchange_order_id,
            reason=f"ACK from {order.broker}",
            transition=result,
        )
