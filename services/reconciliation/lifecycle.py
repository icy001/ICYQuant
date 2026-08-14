"""Reconciliation lifecycle state machine (Commit 40 Part 1.5).

A reconciliation no longer only reports ``MATCHED`` or ``MISMATCH``; it now
travels through a full lifecycle:

    CREATED
        -> RUNNING
            -> MATCHED
            -> MISMATCHED
                -> REPAIR_PLANNED
                    -> REPAIRING
                        -> VERIFYING
                            -> RECOVERED
                            -> FAILED
                            -> MANUAL_REVIEW
                -> MANUAL_REVIEW
"""

from __future__ import annotations

from .models.status import ReconciliationLifecycle


class InvalidLifecycleTransition(Exception):  # noqa: N818
    """Raised when a lifecycle transition is not allowed."""


class ReconciliationLifecycleManager:
    _allowed = {
        ReconciliationLifecycle.CREATED: {
            ReconciliationLifecycle.RUNNING,
        },
        ReconciliationLifecycle.RUNNING: {
            ReconciliationLifecycle.MATCHED,
            ReconciliationLifecycle.MISMATCHED,
        },
        ReconciliationLifecycle.MISMATCHED: {
            ReconciliationLifecycle.REPAIR_PLANNED,
            ReconciliationLifecycle.MANUAL_REVIEW,
        },
        ReconciliationLifecycle.REPAIR_PLANNED: {
            ReconciliationLifecycle.REPAIRING,
        },
        ReconciliationLifecycle.REPAIRING: {
            ReconciliationLifecycle.VERIFYING,
            ReconciliationLifecycle.FAILED,
        },
        ReconciliationLifecycle.VERIFYING: {
            ReconciliationLifecycle.RECOVERED,
            ReconciliationLifecycle.FAILED,
            ReconciliationLifecycle.MANUAL_REVIEW,
        },
    }

    def __init__(
        self,
        initial: ReconciliationLifecycle = ReconciliationLifecycle.CREATED,
    ) -> None:
        self._state = initial

    @property
    def state(self) -> ReconciliationLifecycle:
        return self._state

    def transition(
        self,
        current: ReconciliationLifecycle,
        target: ReconciliationLifecycle,
    ) -> ReconciliationLifecycle:
        allowed = self._allowed.get(current, set())

        if target not in allowed:
            raise InvalidLifecycleTransition(
                f"Invalid transition: {current} -> {target}"
            )

        return target

    def advance(
        self,
        target: ReconciliationLifecycle,
    ) -> ReconciliationLifecycle:
        self._state = self.transition(self._state, target)
        return self._state
