"""Recovery engine — determine, reconcile, then decide retry (Commit 29 Part 1.3 §19-29).

Recovery is not retry. The priority is (§20)::

    1. Determine actual state
    2. Reconcile with the target
    3. Decide whether a retry is allowed

An UNKNOWN outcome is never blind-retried (§16); a TIMEOUT is not a FAILURE
(§15); a crash in EXECUTING is RECOVERY_REQUIRED, not FAILED (§24-25).

Note: the Part 1.3 spec names this module ``recovery.py``; it is shipped as
``recovery_engine.py`` so it does not shadow the existing ``recovery/``
package.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from .execution_attempt import ExecutionState
from .store import CommandStore
from .timeout import RetryPolicy


class RecoveryAction(str, Enum):
    """What the recovery engine decided to do next (§19-20, §26)."""

    RECONCILE = "RECONCILE"
    RETRY = "RETRY"
    SUCCEED = "SUCCEED"
    RESTART = "RESTART"
    NO_ACTION = "NO_ACTION"
    MANUAL_INTERVENTION = "MANUAL_INTERVENTION"


@dataclass(frozen=True)
class RecoveryDecision:
    """Outcome of a recovery decision (§19-20)."""

    action: str
    state: str
    reason: str
    attempt_id: str | None = None


class RecoverableControlHandler(Protocol):
    """A control handler that can report the target's actual state (§22)."""

    def query_status(self, command: Any) -> str: ...


class ControlRecovery:
    """Recovery engine with a fail-closed retry policy (§19-29)."""

    def __init__(
        self,
        *,
        retry_policy: RetryPolicy | None = None,
        applied_targets: dict[str, str] | None = None,
    ) -> None:
        self.retry_policy = retry_policy
        # resource:action -> expected target state, e.g. {"trading:pause": "PAUSED"}
        self.applied_targets = dict(applied_targets or {})

    def recover(
        self,
        command: Any,
        attempt: Any,
    ) -> RecoveryDecision:
        """Decide the recovery step for one finished attempt (§19, §40)."""
        if attempt.state in (
            ExecutionState.UNKNOWN,
            ExecutionState.TIMED_OUT,
        ):
            # §15-16: timeout != failure; unknown cannot blind-retry.
            return RecoveryDecision(
                action=RecoveryAction.RECONCILE.value,
                state="RECOVERY_REQUIRED",
                reason=(
                    "execution outcome is indeterminate: "
                    "reconcile with the target before any retry"
                ),
                attempt_id=attempt.attempt_id,
            )
        if attempt.state == ExecutionState.FAILED:
            return self.retry_if_allowed(command, attempt)
        if attempt.state == ExecutionState.SUCCEEDED:
            return RecoveryDecision(
                action=RecoveryAction.NO_ACTION.value,
                state="SUCCEEDED",
                reason="attempt already succeeded",
                attempt_id=attempt.attempt_id,
            )
        return RecoveryDecision(
            action=RecoveryAction.NO_ACTION.value,
            state=getattr(command, "state", "UNKNOWN"),
            reason="attempt is not in a recoverable state",
            attempt_id=attempt.attempt_id,
        )

    def retry_if_allowed(
        self,
        command: Any,
        attempt: Any | None = None,
    ) -> RecoveryDecision:
        """Retry only when an explicit policy allows it (fail closed, §27)."""
        if self.retry_policy is None:
            allowed = False
        elif attempt is not None:
            allowed = self.retry_policy.can_retry(
                attempt.attempt_number,
                attempt.error_code,
            )
        else:
            # Target confirmed NOT_APPLIED: a fresh dispatch is safe and does
            # not risk duplicate execution (§26).
            allowed = True
        if not allowed:
            return RecoveryDecision(
                action=RecoveryAction.MANUAL_INTERVENTION.value,
                state="MANUAL_INTERVENTION",
                reason="retry policy forbids automatic retry",
                attempt_id=getattr(attempt, "attempt_id", None),
            )
        return RecoveryDecision(
            action=RecoveryAction.RETRY.value,
            state="AUTHORIZED",
            reason="retry allowed by policy",
            attempt_id=getattr(attempt, "attempt_id", None),
        )

    def reconcile(
        self,
        command: Any,
        target_state: str,
        *,
        applied: bool | None = None,
        attempt: Any | None = None,
    ) -> RecoveryDecision:
        """Reconcile the command against the target's actual state (§21, §26, §41).

        * ``applied=True`` (or ``target_state`` matching the configured
          expected state) -> SUCCEEDED
        * NOT_APPLIED -> retry only if the policy allows it
        * no mapping configured -> MANUAL_INTERVENTION (cannot determine)
        """
        if applied is None:
            expected = self.applied_targets.get(
                f"{command.resource}:{command.action}"
            )
            if expected is None:
                return RecoveryDecision(
                    action=RecoveryAction.MANUAL_INTERVENTION.value,
                    state="MANUAL_INTERVENTION",
                    reason=(
                        "cannot determine whether the target applied the command"
                    ),
                )
            applied = target_state == expected
        if applied:
            return RecoveryDecision(
                action=RecoveryAction.SUCCEED.value,
                state="SUCCEEDED",
                reason=f"target already applied: {target_state}",
            )
        return self.retry_if_allowed(command, attempt)

    def recover_after_crash(
        self,
        store: CommandStore,
        command_id: str,
    ) -> RecoveryDecision:
        """Crash-recovery entry point (§24-25, §38).

        A command found in EXECUTING / UNKNOWN is indeterminate — the target
        may or may not have executed — so the system must reconcile with the
        target instead of assuming failure.
        """
        record = store.get(command_id)
        if record.state in ("EXECUTING", "UNKNOWN"):
            return RecoveryDecision(
                action=RecoveryAction.RECONCILE.value,
                state="RECOVERY_REQUIRED",
                reason=(
                    f"process crash while {record.state}: "
                    "target state is indeterminate"
                ),
            )
        if record.state in (
            "RECEIVED",
            "AUTHORIZING",
            "WAITING_APPROVAL",
            "AUTHORIZED",
            "DISPATCHING",
        ):
            return RecoveryDecision(
                action=RecoveryAction.RESTART.value,
                state="AUTHORIZED",
                reason="process crash before execution: safe to re-drive",
            )
        return RecoveryDecision(
            action=RecoveryAction.NO_ACTION.value,
            state=record.state,
            reason="terminal state: nothing to recover",
        )
