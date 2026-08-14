"""Execution intent lifecycle state machine.

An execution intent is not a passive record: it moves through a guarded
lifecycle from creation to a terminal state::

    PENDING -> VALIDATED -> SUBMITTED -> (terminal)
                                 \\-> REJECTED / EXPIRED / CANCELLED

Only :class:`IntentLifecycle` may change an intent's state.  Illegal
transitions (e.g. PENDING -> SUBMITTED without validation, or any transition
out of a terminal state) raise :class:`IntentLifecycleError` (a
``ValueError``) so a corrupted state can never reach the risk engine.
"""

from __future__ import annotations

from services.strategy.execution.intent import ExecutionIntentState, intent_state_value


class IntentLifecycleError(ValueError):
    """Raised when an intent cannot make the requested state transition."""


class IntentLifecycle:
    """Guarded state machine for a single execution intent.

    The machine is created in the intent's current state (default PENDING)
    and only accepts transitions listed in :data:`ALLOWED_TRANSITIONS`.
    Terminal states (REJECTED / EXPIRED / CANCELLED) accept no further
    transition.
    """

    #: Allowed intent state transitions.  PENDING must be validated before it
    #: can be submitted; REJECTED / EXPIRED / CANCELLED are terminal.
    ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
        ExecutionIntentState.PENDING.value: frozenset(
            {
                ExecutionIntentState.VALIDATED.value,
                ExecutionIntentState.REJECTED.value,
                ExecutionIntentState.EXPIRED.value,
                ExecutionIntentState.CANCELLED.value,
            }
        ),
        ExecutionIntentState.VALIDATED.value: frozenset(
            {
                ExecutionIntentState.SUBMITTED.value,
                ExecutionIntentState.REJECTED.value,
                ExecutionIntentState.EXPIRED.value,
                ExecutionIntentState.CANCELLED.value,
            }
        ),
        ExecutionIntentState.SUBMITTED.value: frozenset(
            {
                ExecutionIntentState.REJECTED.value,
                ExecutionIntentState.EXPIRED.value,
                ExecutionIntentState.CANCELLED.value,
            }
        ),
        ExecutionIntentState.REJECTED.value: frozenset(),
        ExecutionIntentState.EXPIRED.value: frozenset(),
        ExecutionIntentState.CANCELLED.value: frozenset(),
    }

    def __init__(
        self,
        intent_id: str,
        state: "str | ExecutionIntentState" = ExecutionIntentState.PENDING,
    ) -> None:
        if not intent_id:
            raise ValueError("intent_id is required")
        self.intent_id = intent_id
        self._state = intent_state_value(state)

    @property
    def state(self) -> str:
        """Current intent state as a plain string."""
        return self._state

    def transition(self, target: "str | ExecutionIntentState") -> str:
        """Move the intent to ``target`` or raise ``IntentLifecycleError``.

        Returns the new state (plain string) on success.
        """
        target_value = intent_state_value(target)
        allowed = self.ALLOWED_TRANSITIONS[self._state]
        if target_value not in allowed:
            raise IntentLifecycleError(
                "cannot transition intent %s from %s to %s"
                % (self.intent_id, self._state, target_value)
            )
        self._state = target_value
        return self._state

    def can_transition(self, target: "str | ExecutionIntentState") -> bool:
        """Return True when ``target`` is reachable from the current state."""
        return intent_state_value(target) in self.ALLOWED_TRANSITIONS[self._state]

    def validate(self) -> str:
        """Convenience: move the intent to VALIDATED."""
        return self.transition(ExecutionIntentState.VALIDATED)

    def submit(self) -> str:
        """Convenience: move the intent to SUBMITTED."""
        return self.transition(ExecutionIntentState.SUBMITTED)

    def reject(self) -> str:
        """Convenience: move the intent to REJECTED."""
        return self.transition(ExecutionIntentState.REJECTED)

    def expire(self) -> str:
        """Convenience: move the intent to EXPIRED."""
        return self.transition(ExecutionIntentState.EXPIRED)

    def cancel(self) -> str:
        """Convenience: move the intent to CANCELLED."""
        return self.transition(ExecutionIntentState.CANCELLED)
