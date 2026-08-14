"""Risk cooldown, hysteresis and breach recovery (Commit 37 Part 1.4).

Prevents Risk Flapping by separating the *risk control lifecycle* (``RiskState``)
from the point-in-time *risk decision*:

.. code-block:: text

    CRITICAL / BREACHED
              |
              | falls below recovery_threshold
              v
          RECOVERING        (requires N consecutive checks)
              |
              | required_recovery_checks reached
              v
          COOLDOWN          (requires cooldown_seconds to elapse)
              |
              | cooldown elapsed
              v
           NORMAL

``RecoveryContext`` carries the mutable lifecycle state; ``RiskRecoveryEngine``
advances it on each ``update`` and can build a full ``RiskRecoveryResult`` for
downstream audit / monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from time import time

from .models import (
    RecoveryAction,
    RiskRecoveryPolicy,
    RiskRecoveryResult,
    RiskState,
)


@dataclass
class RecoveryContext:

    state: RiskState = RiskState.NORMAL

    recovery_checks: int = 0

    cooldown_started_at: float | None = None


class RiskRecoveryEngine:

    def update(
        self,
        *,
        context: RecoveryContext,
        risk_value: Decimal,
        policy: RiskRecoveryPolicy,
        now: float | None = None,
    ) -> RiskState:

        if not policy.enabled:
            context.state = RiskState.NORMAL
            context.recovery_checks = 0
            context.cooldown_started_at = None
            return context.state

        current_time = (
            time()
            if now is None
            else now
        )

        if (
            risk_value
            >= policy.recovery_threshold
        ):
            context.recovery_checks = 0
            context.cooldown_started_at = None

            return context.state

        if context.state in (
            RiskState.CRITICAL,
            RiskState.BREACHED,
        ):
            context.state = (
                RiskState.RECOVERING
            )

        if context.state == RiskState.RECOVERING:

            context.recovery_checks += 1

            if (
                context.recovery_checks
                >= policy.required_recovery_checks
            ):
                context.state = (
                    RiskState.COOLDOWN
                )

                context.cooldown_started_at = (
                    current_time
                )

        elif context.state == RiskState.COOLDOWN:

            if (
                context.cooldown_started_at
                is not None
                and current_time
                - context.cooldown_started_at
                >= policy.cooldown_seconds
            ):
                context.state = RiskState.NORMAL
                context.recovery_checks = 0
                context.cooldown_started_at = None

        return context.state

    def action_for_state(
        self,
        state: RiskState,
    ) -> RecoveryAction:

        if state == RiskState.CRITICAL:
            return RecoveryAction.CONTINUE_BLOCK

        if state in (
            RiskState.BREACHED,
            RiskState.RECOVERING,
        ):
            return RecoveryAction.REDUCE_ONLY

        if state == RiskState.COOLDOWN:
            return RecoveryAction.COOLDOWN

        if state == RiskState.NORMAL:
            return RecoveryAction.RESTORE

        return RecoveryAction.NONE

    def build_result(
        self,
        *,
        previous_state: RiskState,
        context: RecoveryContext,
        policy: RiskRecoveryPolicy,
        now: float | None = None,
    ) -> RiskRecoveryResult:

        current_time = (
            time()
            if now is None
            else now
        )

        cooldown_remaining = 0
        if (
            context.state == RiskState.COOLDOWN
            and context.cooldown_started_at
            is not None
        ):
            cooldown_remaining = max(
                0,
                policy.cooldown_seconds
                - int(
                    current_time
                    - context.cooldown_started_at
                ),
            )

        recovered = (
            previous_state != RiskState.NORMAL
            and context.state == RiskState.NORMAL
        )

        return RiskRecoveryResult(
            previous_state=previous_state,
            current_state=context.state,
            action=self.action_for_state(
                context.state
            ),
            recovery_checks=context.recovery_checks,
            cooldown_remaining_seconds=(
                cooldown_remaining
            ),
            recovered=recovered,
        )
