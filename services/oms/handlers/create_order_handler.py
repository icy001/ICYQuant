"""CreateOrderHandler — handles CreateOrderCommand."""
from __future__ import annotations

import uuid

from services.oms.commands.create_order import CreateOrderCommand
from services.oms.events.order_event_type import OrderEventType
from services.oms.events.order_event_factory import OrderEventFactory
from services.oms.results.command_result import CommandResult
from services.oms.results.command_errors import DuplicateCommandError
from .command_handler import CommandHandler


class CreateOrderHandler(CommandHandler):
    """Handles CreateOrderCommand — creates a new order.

    Flow:
      1. Check client_order_id idempotency
      2. Generate order_id
      3. Emit ORDER_ACCEPTED event
      4. Emit ORDER_CREATED event
      5. Return result with order_id
    """

    def handle(self, command: CreateOrderCommand) -> CommandResult:
        # Check client_order_id idempotency via existing streams
        if command.client_order_id:
            for oid in self._store.get_all_order_ids():
                events = self._store.read(oid)
                for evt in events:
                    if (evt.event_type == OrderEventType.ORDER_CREATED
                            and evt.payload.get("client_order_id")
                            == command.client_order_id):
                        raise DuplicateCommandError(
                            command.command_id, existing_order_id=oid,
                        )

        # Generate order_id
        order_id = command.order_id or (
            f"ORD-{uuid.uuid4().hex[:12].upper()}"
        )

        # Build metadata
        meta = self._make_event_metadata(command)

        # Get lineage from command
        lineage_id = command.lineage_id
        flow_id = command.flow_id
        cert_id = command.certificate_id

        # Sequence 1: ORDER_ACCEPTED
        seq1 = 1
        event1 = OrderEventFactory.accepted(
            order_id=order_id, sequence=seq1,
            lineage_id=lineage_id, flow_id=flow_id,
            certificate_id=cert_id,
            metadata=meta,
        )
        self._append_and_project(event1)

        # Sequence 2: ORDER_CREATED
        seq2 = 2
        event2 = OrderEventFactory.created(
            order_id=order_id, sequence=seq2,
            symbol=command.symbol, side=command.side,
            order_type=command.order_type,
            quantity=command.quantity, price=command.price,
            lineage_id=lineage_id, flow_id=flow_id,
            certificate_id=cert_id,
            metadata=meta,
            previous_hash=event1.event_hash,
        )
        # Add client_order_id to payload
        event2.payload["client_order_id"] = command.client_order_id
        event2.payload["account_id"] = command.account_id
        event2.payload["strategy_id"] = command.strategy_id
        event2.payload["time_in_force"] = command.time_in_force
        self._append_and_project(event2)

        return CommandResult.ok(
            command_id=command.command_id,
            order_id=order_id,
            event_id=event2.event_id,
            event_sequence=seq2,
            status="CREATED",
        )
