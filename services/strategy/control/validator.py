"""Strategy control validator.

The validator is the single enforcement point for the strategy state
machine: it rejects any action that is not legal from the current
control state.  Illegal transitions (e.g. ``STOPPED -> pause`` or
``KILLED -> resume``) raise ``ValueError`` and never reach the control
plane.
"""

from __future__ import annotations

from services.strategy.control.policies import ALLOWED_ACTIONS_BY_STATE
from services.strategy.domain.control_state import StrategyControlState

StateLike = "str | StrategyControlState"


def _state_value(state: StateLike) -> str:
    return state.value if isinstance(state, StrategyControlState) else state


class StrategyControlValidator:
    """Rejects strategy control actions illegal from the current state."""

    def validate(self, state: StateLike, action: str) -> None:
        current = _state_value(state)
        allowed = ALLOWED_ACTIONS_BY_STATE.get(current)
        if allowed is None or action not in allowed:
            raise ValueError(
                f"invalid strategy transition: {current} -> {action}"
            )
