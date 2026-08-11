"""CancellationHandler — handles cancel, reject, and expire commands."""
from __future__ import annotations

from services.oms.commands.request_cancel import RequestCancelCommand
from services.oms.commands.confirm_cancel import ConfirmCancelCommand
from services.oms.commands.reject_order import RejectOrderCommand
from services.oms.commands.expire_order import ExpireOrderCommand
from services.oms.events.order_event_factory import OrderEventFactory
from services.oms.results.command_result import CommandResult
from services.oms.results.command_errors import InvalidStateTransitionError
from services.oms.validation.lifecycle_validator import LifecycleValidator
from services.oms.validation.concurrency_validator import ConcurrencyValidator
from .command_handler import CommandHandler


class CancellationHandler(CommandHandler):
    """Handles RequestCancel, ConfirmCancel, RejectOrder, ExpireOrder."""

    def handle(self, command) -> CommandResult:
        if isinstance(command, RequestCancelCommand):
            return self._handle_request_cancel(command)
        elif isinstance(command, ConfirmCancelCommand):
            return self._handle_confirm_cancel(command)
        elif isinstance(command, RejectOrderCommand):
            return self._handle_reject(command)
        elif isinstance(command, ExpireOrderCommand):
            return self._handle_expire(command)
        else:
            return CommandResult.fail(
                command.command_id, "UNKNOWN_COMMAND",
                f"Unknown command type: {type(command).__name__}",
            )

    def _handle_request_cancel(self, cmd: RequestCancelCommand) -> CommandResult:
        proj = self._get_projection(cmd.order_id)

        ConcurrencyValidator.validate(
            cmd.command_id, cmd.order_id,
            cmd.expected_version or 0, proj.last_event_sequence,
        )

        if not LifecycleValidator.can_cancel(proj.status):
            raise InvalidStateTransitionError(
                cmd.command_id, cmd.order_id,
                proj.status.name, "REQUEST_CANCEL",
            )

        seq = self._get_next_sequence(cmd.order_id)
        meta = self._make_event_metadata(cmd)
        event = OrderEventFactory.cancel_requested(
            order_id=cmd.order_id, sequence=seq,
            reason=cmd.reason,
            lineage_id=proj.lineage_id,
            flow_id=proj.flow_id,
            certificate_id=proj.certificate_id,
            metadata=meta,
            previous_hash=proj.last_event_hash,
        )
        self._append_and_project(event)

        return CommandResult.ok(
            command_id=cmd.command_id, order_id=cmd.order_id,
            event_id=event.event_id, event_sequence=seq,
            status=proj.status.name,  # status doesn't change
        )

    def _handle_confirm_cancel(self, cmd: ConfirmCancelCommand) -> CommandResult:
        proj = self._get_projection(cmd.order_id)

        ConcurrencyValidator.validate(
            cmd.command_id, cmd.order_id,
            cmd.expected_version or 0, proj.last_event_sequence,
        )

        LifecycleValidator.validate_transition(
            "CONFIRM_CANCEL", proj.status, cmd.order_id, cmd.command_id,
        )

        cancelled_qty = cmd.cancelled_quantity or proj.remaining_quantity
        seq = self._get_next_sequence(cmd.order_id)
        meta = self._make_event_metadata(cmd)
        event = OrderEventFactory.cancelled(
            order_id=cmd.order_id, sequence=seq,
            cancelled_quantity=cancelled_qty,
            reason=cmd.reason,
            lineage_id=proj.lineage_id,
            flow_id=proj.flow_id,
            certificate_id=proj.certificate_id,
            metadata=meta,
            previous_hash=proj.last_event_hash,
        )
        self._append_and_project(event)

        return CommandResult.ok(
            command_id=cmd.command_id, order_id=cmd.order_id,
            event_id=event.event_id, event_sequence=seq,
            status="CANCELLED",
        )

    def _handle_reject(self, cmd: RejectOrderCommand) -> CommandResult:
        proj = self._get_projection(cmd.order_id)

        ConcurrencyValidator.validate(
            cmd.command_id, cmd.order_id,
            cmd.expected_version or 0, proj.last_event_sequence,
        )

        if not LifecycleValidator.can_reject(proj.status):
            raise InvalidStateTransitionError(
                cmd.command_id, cmd.order_id,
                proj.status.name, "REJECT_ORDER",
            )

        seq = self._get_next_sequence(cmd.order_id)
        meta = self._make_event_metadata(cmd)
        event = OrderEventFactory.rejected(
            order_id=cmd.order_id, sequence=seq,
            reason=f"{cmd.reject_code}: {cmd.reject_reason}",
            lineage_id=proj.lineage_id,
            flow_id=proj.flow_id,
            certificate_id=proj.certificate_id,
            metadata=meta,
            previous_hash=proj.last_event_hash,
        )
        event.payload["reject_code"] = cmd.reject_code
        event.payload["execution_source"] = cmd.execution_source
        self._append_and_project(event)

        return CommandResult.ok(
            command_id=cmd.command_id, order_id=cmd.order_id,
            event_id=event.event_id, event_sequence=seq,
            status="REJECTED",
        )

    def _handle_expire(self, cmd: ExpireOrderCommand) -> CommandResult:
        proj = self._get_projection(cmd.order_id)

        ConcurrencyValidator.validate(
            cmd.command_id, cmd.order_id,
            cmd.expected_version or 0, proj.last_event_sequence,
        )

        if not LifecycleValidator.can_expire(proj.status):
            raise InvalidStateTransitionError(
                cmd.command_id, cmd.order_id,
                proj.status.name, "EXPIRE_ORDER",
            )

        seq = self._get_next_sequence(cmd.order_id)
        meta = self._make_event_metadata(cmd)
        event = OrderEventFactory.expired(
            order_id=cmd.order_id, sequence=seq,
            lineage_id=proj.lineage_id,
            flow_id=proj.flow_id,
            certificate_id=proj.certificate_id,
            metadata=meta,
            previous_hash=proj.last_event_hash,
        )
        self._append_and_project(event)

        return CommandResult.ok(
            command_id=cmd.command_id, order_id=cmd.order_id,
            event_id=event.event_id, event_sequence=seq,
            status="EXPIRED",
        )
