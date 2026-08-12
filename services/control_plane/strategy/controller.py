"""
StrategyController — per-strategy trading capability gate
(Commit 26 Part 1.3, spec sections 6–8).

Strategy Control sits *before* the Signal Generator:

    Strategy Runtime
          ↓
    Strategy Controller
          │
          ├── ALLOW  →  Signal Generator
          └── BLOCK  →  No Signal

Pausing or disabling a strategy therefore prevents invalid computation,
meaningless events, useless order requests, Risk Engine pressure and OMS
garbage — instead of letting orders flow and being stopped at the Gateway.

``RECOVERING`` intentionally evaluates as fail-closed (no trading capability)
until an authorized operator explicitly returns the strategy to RUNNING.
"""

from __future__ import annotations

from uuid import UUID

from .audit import (
    StrategyControlAuditRecord,
    audit_event_type_for,
)
from .decision import StrategyControlDecision
from .policy import StrategyControlPolicy
from .state import StrategyState


class StrategyController:

    def __init__(
        self,
        policy: StrategyControlPolicy | None = None,
    ) -> None:

        self.policy = (
            policy
            or StrategyControlPolicy()
        )

        self._states: dict[str, StrategyState] = {}

        self._audit_trail: list[StrategyControlAuditRecord] = []

    def state(
        self,
        strategy_id: str,
    ) -> StrategyState:

        return self._states.get(
            strategy_id,
            StrategyState.RUNNING,
        )

    def set_state(
        self,
        strategy_id: str,
        state: StrategyState,
        *,
        incident_id: UUID | None = None,
        control_id: UUID | None = None,
        actor: str = "strategy-controller",
        reason: str = "",
    ) -> None:

        previous_state = self.state(strategy_id)
        self._states[strategy_id] = state

        if previous_state is not state:
            self._audit_trail.append(
                StrategyControlAuditRecord(
                    event_type=audit_event_type_for(state),
                    strategy_id=strategy_id,
                    previous_state=previous_state,
                    new_state=state,
                    incident_id=incident_id,
                    control_id=control_id,
                    actor=actor,
                    reason=reason,
                )
            )

    def evaluate(
        self,
        strategy_id: str,
    ) -> StrategyControlDecision:

        state = self.state(strategy_id)

        if state == StrategyState.RUNNING:

            return StrategyControlDecision(
                strategy_id=strategy_id,
                current_state=state,
                allow_signal_generation=True,
                allow_new_orders=True,
                allow_reduce_orders=True,
                reason="strategy_running",
            )

        if state == StrategyState.PAUSED:

            return StrategyControlDecision(
                strategy_id=strategy_id,
                current_state=state,
                allow_signal_generation=False,
                allow_new_orders=False,
                allow_reduce_orders=(
                    self.policy.paused_allow_reduce
                ),
                reason="strategy_paused",
            )

        if state == StrategyState.DRAINING:

            return StrategyControlDecision(
                strategy_id=strategy_id,
                current_state=state,
                allow_signal_generation=False,
                allow_new_orders=False,
                allow_reduce_orders=(
                    self.policy.draining_allow_reduce
                ),
                reason="strategy_draining",
            )

        if state == StrategyState.DISABLED:

            return StrategyControlDecision(
                strategy_id=strategy_id,
                current_state=state,
                allow_signal_generation=(
                    self.policy.disabled_allow_signal
                ),
                allow_new_orders=False,
                allow_reduce_orders=(
                    self.policy.disabled_allow_reduce
                ),
                reason="strategy_disabled",
            )

        return StrategyControlDecision(
            strategy_id=strategy_id,
            current_state=state,
            allow_signal_generation=False,
            allow_new_orders=False,
            allow_reduce_orders=False,
            reason="unknown_strategy_state",
        )

    @property
    def audit_trail(
        self,
    ) -> list[StrategyControlAuditRecord]:
        """Immutable view of the state-transition audit trail."""
        return list(self._audit_trail)
