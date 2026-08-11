"""RoutingHandler — handles StartRoutingCommand and MarkWorkingCommand."""
from __future__ import annotations

from services.oms.commands.start_routing import StartRoutingCommand
from services.oms.commands.mark_working import MarkWorkingCommand
from services.oms.domain.order_status import OrderStatus
from services.oms.events.order_event_factory import OrderEventFactory
from services.oms.results.command_result import CommandResult
from services.oms.results.command_errors import InvalidStateTransitionError
from services.oms.validation.lifecycle_validator import LifecycleValidator
from services.oms.validation.concurrency_validator import ConcurrencyValidator
from .command_handler import CommandHandler


class RoutingHandler(CommandHandler):
    """Handles StartRoutingCommand and MarkWorkingCommand."""

    def handle(self, command) -> CommandResult:
        if isinstance(command, StartRoutingCommand):
            return self._handle_start_routing(command)
        elif isinstance(command, MarkWorkingCommand):
            return self._handle_mark_working(command)
        else:
            return CommandResult.fail(
                command.command_id, "UNKNOWN_COMMAND",
                f"Unknown command type: {type(command).__name__}",
            )

    def _handle_start_routing(self, cmd: StartRoutingCommand) -> CommandResult:
        proj = self._get_projection(cmd.order_id)

        # Concurrency check
        ConcurrencyValidator.validate(
            cmd.command_id, cmd.order_id,
            cmd.expected_version or 0, proj.last_event_sequence,
        )

        # Lifecycle check
        LifecycleValidator.validate_transition(
            "START_ROUTING", proj.status, cmd.order_id, cmd.command_id,
        )

        # Generate event
        seq = self._get_next_sequence(cmd.order_id)
        meta = self._make_event_metadata(cmd)
        event = OrderEventFactory.routing_started(
            order_id=cmd.order_id, sequence=seq,
            route=cmd.route,
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
            status="ROUTING",
        )

    def _handle_mark_working(self, cmd: MarkWorkingCommand) -> CommandResult:
        proj = self._get_projection(cmd.order_id)

        ConcurrencyValidator.validate(
            cmd.command_id, cmd.order_id,
            cmd.expected_version or 0, proj.last_event_sequence,
        )

        LifecycleValidator.validate_transition(
            "MARK_WORKING", proj.status, cmd.order_id, cmd.command_id,
        )

        seq = self._get_next_sequence(cmd.order_id)
        meta = self._make_event_metadata(cmd)
        event = OrderEventFactory.working(
            order_id=cmd.order_id, sequence=seq,
            venue=cmd.venue,
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
            status="WORKING",
        )
