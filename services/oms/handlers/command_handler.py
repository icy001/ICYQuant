"""CommandHandler — base class for all command handlers.

Standard flow:
    Receive Command
         ↓
    Load Aggregate (from event store)
         ↓
    Validate Command
         ↓
    Validate State (lifecycle)
         ↓
    Execute Domain Logic
         ↓
    Generate Events
         ↓
    Append Events
         ↓
    Update Projection
         ↓
    Return Result
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from services.oms.commands.order_command import OrderCommand
from services.oms.events.order_event import OrderEvent
from services.oms.events.order_event_factory import OrderEventFactory
from services.oms.event_store.order_event_store import OrderEventStore
from services.oms.event_store.event_stream_writer import EventStreamWriter
from services.oms.projection.order_projector import OrderProjector
from services.oms.projection.order_projection import OrderProjection
from services.oms.results.command_result import CommandResult
from services.oms.results.command_errors import (
    DuplicateCommandError,
    CommandError,
)
from services.oms.validation.command_validator import CommandValidator
from services.oms.validation.lifecycle_validator import LifecycleValidator
from services.oms.validation.concurrency_validator import ConcurrencyValidator


class CommandHandler(ABC):
    """Base class for all command handlers.

    Subclasses implement `handle()` which validates the command,
    generates events, and returns a CommandResult.
    """

    def __init__(self, store: OrderEventStore,
                 projector: OrderProjector,
                 command_cache: Optional[Dict[str, CommandResult]] = None) -> None:
        self._store = store
        self._writer = EventStreamWriter(store)
        self._projector = projector
        self._command_cache = command_cache if command_cache is not None else {}

    def execute(self, command: OrderCommand) -> CommandResult:
        """Execute a command with idempotency and validation.

        Flow:
          1. Check idempotency (command_id cache)
          2. Validate command fields
          3. Delegate to subclass handle()
          4. Cache result
        """
        # Idempotency check
        if command.command_id in self._command_cache:
            return CommandResult.idempotent_replay(
                self._command_cache[command.command_id],
            )

        try:
            # Validate command fields
            CommandValidator.validate(command)

            # Delegate to subclass
            result = self.handle(command)

            # Cache result
            self._command_cache[command.command_id] = result
            return result

        except CommandError as e:
            result = CommandResult.fail(
                command.command_id, e.code, e.message,
                order_id=e.order_id,
            )
            self._command_cache[command.command_id] = result
            return result

        except Exception as e:
            result = CommandResult.fail(
                command.command_id, "UNKNOWN_ERROR", str(e),
            )
            return result

    @abstractmethod
    def handle(self, command: OrderCommand) -> CommandResult:
        """Subclass-specific command handling logic."""

    # ── Helpers ────────────────────────────────────

    def _get_next_sequence(self, order_id: str) -> int:
        """Get the next sequence number for an order."""
        return self._store.get_latest_sequence(order_id) + 1

    def _get_projection(self, order_id: str) -> OrderProjection:
        """Get the current projection for an order."""
        return self._projector.get_or_rebuild(order_id)

    def _append_and_project(self, event: OrderEvent) -> None:
        """Append an event to the store and update the projection."""
        self._store.append(event)
        self._projector.apply_event(event)

    def _make_event_metadata(self, command: OrderCommand):
        """Create event metadata from command context."""
        from services.oms.events.order_event_metadata import OrderEventMetadata
        return OrderEventMetadata(
            actor_type=command.actor_type,
            actor_id=command.actor_id,
            source=command.metadata.source,
            correlation_id=command.correlation_id,
            causation_id=command.causation_id,
            request_id=command.metadata.request_id,
        )
