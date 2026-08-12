"""
ExecutionController — per-execution-channel capability gate
(Commit 26 Part 1.4, spec section 6).

Execution Control decides four capabilities independently:

    New Order
    Cancel Order
    Reduce Order
    Emergency Flatten

The unknown / unhandled state intentionally evaluates as fail-closed
(everything blocked), because an unrecognized execution state must never
silently allow orders through.
"""

from __future__ import annotations

from uuid import UUID

from .audit import (
    ExecutionControlAuditRecord,
    audit_event_type_for,
)
from .decision import ExecutionControlDecision
from .policy import ExecutionControlPolicy
from .state import ExecutionState


class ExecutionController:

    def __init__(
        self,
        policy: ExecutionControlPolicy | None = None,
    ) -> None:

        self.policy = (
            policy
            or ExecutionControlPolicy()
        )

        self._states: dict[str, ExecutionState] = {}

        self._audit_trail: list[ExecutionControlAuditRecord] = []

    def state(
        self,
        execution_id: str,
    ) -> ExecutionState:

        return self._states.get(
            execution_id,
            ExecutionState.ACTIVE,
        )

    def set_state(
        self,
        execution_id: str,
        state: ExecutionState,
        *,
        incident_id: UUID | None = None,
        control_id: UUID | None = None,
        venue: str | None = None,
        actor: str = "execution-controller",
        reason: str = "",
    ) -> None:

        previous_state = self.state(execution_id)
        self._states[execution_id] = state

        if previous_state is not state:
            self._audit_trail.append(
                ExecutionControlAuditRecord(
                    event_type=audit_event_type_for(state),
                    execution_id=execution_id,
                    previous_state=previous_state,
                    new_state=state,
                    incident_id=incident_id,
                    control_id=control_id,
                    venue=venue,
                    actor=actor,
                    reason=reason,
                )
            )

    def evaluate(
        self,
        execution_id: str,
    ) -> ExecutionControlDecision:

        state = self.state(execution_id)

        if state == ExecutionState.ACTIVE:

            return ExecutionControlDecision(
                execution_id=execution_id,
                state=state,
                allow_new_orders=True,
                allow_cancel_orders=True,
                allow_reduce_orders=True,
                allow_emergency_flatten=True,
                reason="execution_active",
            )

        if state == ExecutionState.DEGRADED:

            return ExecutionControlDecision(
                execution_id=execution_id,
                state=state,
                allow_new_orders=(
                    self.policy.degraded_allow_new
                ),
                allow_cancel_orders=True,
                allow_reduce_orders=True,
                allow_emergency_flatten=True,
                reason="execution_degraded",
            )

        if state == ExecutionState.PAUSED:

            return ExecutionControlDecision(
                execution_id=execution_id,
                state=state,
                allow_new_orders=False,
                allow_cancel_orders=(
                    self.policy.paused_allow_cancel
                ),
                allow_reduce_orders=(
                    self.policy.paused_allow_reduce
                ),
                allow_emergency_flatten=True,
                reason="execution_paused",
            )

        if state == ExecutionState.DRAINING:

            return ExecutionControlDecision(
                execution_id=execution_id,
                state=state,
                allow_new_orders=False,
                allow_cancel_orders=(
                    self.policy.draining_allow_cancel
                ),
                allow_reduce_orders=(
                    self.policy.draining_allow_reduce
                ),
                allow_emergency_flatten=True,
                reason="execution_draining",
            )

        if state == ExecutionState.DISABLED:

            return ExecutionControlDecision(
                execution_id=execution_id,
                state=state,
                allow_new_orders=False,
                allow_cancel_orders=(
                    self.policy.disabled_allow_cancel
                ),
                allow_reduce_orders=False,
                allow_emergency_flatten=(
                    self.policy
                    .disabled_allow_emergency_flatten
                ),
                reason="execution_disabled",
            )

        if state == ExecutionState.FAILOVER:

            return ExecutionControlDecision(
                execution_id=execution_id,
                state=state,
                allow_new_orders=False,
                allow_cancel_orders=True,
                allow_reduce_orders=False,
                allow_emergency_flatten=True,
                reason="execution_failover",
            )

        return ExecutionControlDecision(
            execution_id=execution_id,
            state=state,
            allow_new_orders=False,
            allow_cancel_orders=False,
            allow_reduce_orders=False,
            allow_emergency_flatten=False,
            reason="unknown_execution_state",
        )

    @property
    def audit_trail(
        self,
    ) -> list[ExecutionControlAuditRecord]:
        """Immutable view of the state-transition audit trail."""
        return list(self._audit_trail)
