"""Strategy control boundary.

The boundary is the *only* gateway between the strategy domain and the
control plane.  It is responsible for strategy-specific validation
(state machine + capability policy) and delegation to the control plane
dispatcher.  It must NOT re-implement authorization, idempotency, replay
protection, audit or execution claim - those remain owned by the control
plane.

Layering::

    Strategy Domain (state / policy / validator)
        |
        v
    Strategy Control Boundary   <- this module
        |
        v
    Control Plane (auth / idempotency / audit / replay / claim / recovery)
        |
        v
    Strategy Runtime
"""

from __future__ import annotations

from typing import Any, Protocol

from services.strategy.control.commands import StrategyCommand
from services.strategy.control.policies import target_state
from services.strategy.control.result import StrategyControlResult
from services.strategy.control.validator import (
    StateLike,
    StrategyControlValidator,
    _state_value,
)


class CommandDispatcher(Protocol):
    """The control plane dispatcher the boundary delegates to."""

    def dispatch(self, command: StrategyCommand) -> Any:  # pragma: no cover
        ...


class StrategyControlBoundary:
    """Validates strategy commands and delegates them to the control plane."""

    def __init__(
        self,
        validator: StrategyControlValidator,
        command_dispatcher: CommandDispatcher,
    ) -> None:
        self.validator = validator
        self.command_dispatcher = command_dispatcher

    def submit(
        self,
        command: StrategyCommand,
        current_state: StateLike,
    ) -> StrategyControlResult:
        previous = _state_value(current_state)

        self.validator.validate(previous, command.action)

        self.command_dispatcher.dispatch(command)

        return StrategyControlResult(
            command_id=command.command_id,
            strategy_id=command.strategy_id,
            action=command.action,
            previous_state=previous,
            current_state=target_state(command.action),
            accepted=True,
        )
