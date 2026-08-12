"""Recovery gate validation (Commit 26 Part 1.5, spec sections 16-17, 27-28).

Recovery 不能只检查"程序活着"：

    Service = UP  =>  Recovery = OK   ❌

而是应该检查系统各层：Event Bus / Ledger / Position / Orders / Risk /
Strategy / Execution / Venue / Reconciliation。
"""

from __future__ import annotations

from dataclasses import dataclass

from .policy import RecoveryPolicy


@dataclass(frozen=True)
class RecoveryChecks:

    incident_clear: bool

    positions_reconciled: bool

    orders_reconciled: bool

    risk_healthy: bool

    execution_healthy: bool

    venues_healthy: bool

    strategy_state_valid: bool

    event_stream_healthy: bool


class RecoveryGate:

    def __init__(
        self,
        policy: RecoveryPolicy | None = None,
    ) -> None:

        self.policy = (
            policy
            or RecoveryPolicy()
        )

    def validate(
        self,
        checks: RecoveryChecks,
    ) -> bool:

        if (
            self.policy.require_no_open_incident
            and not checks.incident_clear
        ):
            return False

        if (
            self.policy.require_position_reconciled
            and not checks.positions_reconciled
        ):
            return False

        if (
            self.policy.require_orders_reconciled
            and not checks.orders_reconciled
        ):
            return False

        if (
            self.policy.require_risk_healthy
            and not checks.risk_healthy
        ):
            return False

        if (
            self.policy.require_execution_healthy
            and not checks.execution_healthy
        ):
            return False

        if (
            self.policy.require_venue_healthy
            and not checks.venues_healthy
        ):
            return False

        if not checks.strategy_state_valid:
            return False

        if not checks.event_stream_healthy:
            return False

        return True
