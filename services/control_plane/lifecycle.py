"""Command lifecycle — the only place command state may change (Commit 29 Part 1.3 §7).

In production a handler never assigns ``command.state = ...`` directly; every
state change goes through ``CommandLifecycle.move`` so it is validated by the
transition engine before it is durable. The ``command`` argument is a
duck-typed mutable holder (the lifecycle operates on the durable record view);
the frozen ``ControlCommand`` keeps its immutable ``with_state`` copy
semantics for the Part 1.1/1.2 pipeline.
"""

from __future__ import annotations

from typing import Any

from .transition import StateTransitionEngine


class CommandLifecycle:
    """Validated command state movement (§7)."""

    def __init__(self, transition_engine: StateTransitionEngine) -> None:
        self.transition_engine = transition_engine

    def move(self, command: Any, target_state: str) -> Any:
        command.state = self.transition_engine.transition(
            command.state,
            target_state,
        )
        return command
