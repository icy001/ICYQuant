"""Strategy control policies.

Two kinds of policy live here:

* ``StrategyControlPolicy`` - the operator-configurable capability
  switches (which actions are allowed at all).
* The state transition policy - the static table describing which
  actions are legal from which control state, together with the target
  state a dispatched action moves the strategy into.
"""

from __future__ import annotations

from dataclasses import dataclass

# action -> intermediate state reached as soon as the command is accepted
# (see Accepted/Completed separation: PAUSE is accepted as PAUSING, the
# runtime confirms completion later and moves the strategy to PAUSED).
ACTION_TARGET_STATES: dict[str, str] = {
    "start": "STARTING",
    "pause": "PAUSING",
    "resume": "RESUMING",
    "stop": "STOPPING",
    "kill": "KILLED",
}

# state -> set of actions legal from that state.
ALLOWED_ACTIONS_BY_STATE: dict[str, frozenset[str]] = {
    "STOPPED": frozenset({"start", "kill"}),
    "STARTING": frozenset({"kill"}),
    "RUNNING": frozenset({"pause", "stop", "kill"}),
    "PAUSING": frozenset({"kill"}),
    "PAUSED": frozenset({"resume", "stop", "kill"}),
    "RESUMING": frozenset({"kill"}),
    "STOPPING": frozenset({"kill"}),
    "KILLED": frozenset(),
    "FAILED": frozenset({"start", "kill"}),
}


def can_transition(state: str, action: str) -> bool:
    """Return True when ``action`` is legal from ``state``."""
    allowed = ALLOWED_ACTIONS_BY_STATE.get(state, frozenset())
    return action in allowed


def target_state(action: str) -> str:
    """Return the intermediate control state entered when ``action`` is accepted."""
    return ACTION_TARGET_STATES[action]


@dataclass(frozen=True)
class StrategyControlPolicy:
    """Operator-configurable capability switches for strategy control."""

    allow_start: bool = True
    allow_pause: bool = True
    allow_resume: bool = True
    allow_stop: bool = True
    allow_kill: bool = True

    def allows(self, action: str) -> bool:
        """Return True when ``action`` is enabled by this policy."""
        switch = getattr(self, f"allow_{action}", None)
        return bool(switch)
