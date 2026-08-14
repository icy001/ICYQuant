"""Strategy control result.

A control result reports whether the command was *accepted* by the
control boundary, not whether the runtime has already completed the
requested operation.  ``current_state`` therefore carries the
intermediate state (e.g. ``PAUSING`` after an accepted ``pause``), not
the final state (``PAUSED``), until the runtime confirms completion.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyControlResult:
    """Outcome of submitting a strategy control command to the boundary."""

    command_id: str
    strategy_id: str
    action: str

    previous_state: str
    current_state: str

    accepted: bool
    reason: str | None = None
