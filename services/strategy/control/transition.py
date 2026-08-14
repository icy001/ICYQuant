"""Strategy lifecycle transition.

A ``StrategyTransition`` *describes* a control-state change; it never
executes anything.  The runtime action is a separate concern performed by
the ``StrategyRuntimeAdapter`` under the direction of the orchestrator:

    Transition      !=      Runtime Action
    (describes)            (executes)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyTransition:
    """A single, recorded strategy control-state change."""

    strategy_id: str
    command_id: str

    from_state: str
    to_state: str

    action: str
