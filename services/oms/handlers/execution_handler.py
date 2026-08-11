"""ExecutionHandler — handles ApplyExecutionCommand (fills)."""
from __future__ import annotations

from services.oms.commands.apply_execution import ApplyExecutionCommand
from services.oms.domain.order_status import OrderStatus
from services.oms.events.order_event_type import OrderEventType
from services.oms.events.order_event_factory import OrderEventFactory
from services.oms.results.command_result import CommandResult
from services.oms.results.command_errors import (
    ExecutionIdConflictError,
    QuantityExceededError,
    InvalidStateTransitionError,
)
from services.oms.validation.lifecycle_validator import LifecycleValidator
from services.oms.validation.quantity_validator import QuantityValidator
from services.oms.validation.concurrency_validator import ConcurrencyValidator
from .command_handler import CommandHandler


class ExecutionHandler(CommandHandler):
    """Handles ApplyExecutionCommand — applies execution fills.

    Determines whether the fill is partial or full based on
    remaining quantity. Handles duplicate execution_id detection.
    """

    def handle(self, command: ApplyExecutionCommand) -> CommandResult:
        proj = self._get_projection(command.order_id)

        # Concurrency check
        ConcurrencyValidator.validate(
            command.command_id, command.order_id,
            command.expected_version or 0, proj.last_event_sequence,
        )

        # Check execution_id for duplicates
        existing_events = self._store.read(command.order_id)
        for evt in existing_events:
            if evt.event_type in (OrderEventType.ORDER_PARTIAL_FILL,
                                   OrderEventType.ORDER_FILLED):
                if evt.payload.get("execution_id") == command.execution_id:
                    # Check if same payload → idempotent, different → conflict
                    if (evt.payload.get("fill_quantity")
                            == command.fill_quantity
                            and evt.payload.get("fill_price")
                            == command.fill_price):
                        # Idempotent replay
                        return CommandResult.ok(
                            command_id=command.command_id,
                            order_id=command.order_id,
                            event_id=evt.event_id,
                            event_sequence=evt.sequence,
                            status=proj.status.name,
                        )
                    else:
                        raise ExecutionIdConflictError(
                            command.command_id,
                            command.execution_id,
                            command.order_id,
                        )

        # Lifecycle check
        if not LifecycleValidator.can_apply_execution(proj.status):
            raise InvalidStateTransitionError(
                command.command_id, command.order_id,
                proj.status.name, "APPLY_EXECUTION",
            )

        # Quantity check
        QuantityValidator.validate_fill(
            command.order_id, command.command_id,
            command.fill_quantity,
            proj.remaining_quantity,
            proj.original_quantity,
        )

        # Determine if partial or full
        new_filled = proj.filled_quantity + command.fill_quantity
        is_full = new_filled >= proj.original_quantity - 0.0001

        seq = self._get_next_sequence(command.order_id)
        meta = self._make_event_metadata(command)

        if is_full:
            event = OrderEventFactory.filled(
                order_id=command.order_id, sequence=seq,
                fill_quantity=command.fill_quantity,
                fill_price=command.fill_price,
                execution_id=command.execution_id,
                lineage_id=proj.lineage_id,
                flow_id=proj.flow_id,
                certificate_id=proj.certificate_id,
                metadata=meta,
                previous_hash=proj.last_event_hash,
            )
            new_status = "FILLED"
        else:
            event = OrderEventFactory.partial_fill(
                order_id=command.order_id, sequence=seq,
                fill_quantity=command.fill_quantity,
                fill_price=command.fill_price,
                execution_id=command.execution_id,
                lineage_id=proj.lineage_id,
                flow_id=proj.flow_id,
                certificate_id=proj.certificate_id,
                metadata=meta,
                previous_hash=proj.last_event_hash,
            )
            new_status = "PARTIALLY_FILLED"

        self._append_and_project(event)

        return CommandResult.ok(
            command_id=command.command_id,
            order_id=command.order_id,
            event_id=event.event_id,
            event_sequence=seq,
            status=new_status,
        )
