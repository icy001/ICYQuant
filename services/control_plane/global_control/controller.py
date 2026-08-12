"""Global emergency control controller (Commit 26 Part 1.5, spec section 6).

KILLED 不代表"所有交易 API 全部关闭"，而是：

    New Risk        ❌
    New Orders      ❌
    Cancel          ✅
    Reduce          ✅
    Flatten         ✅
"""

from __future__ import annotations

from typing import Callable
from uuid import UUID

from .audit import (
    GlobalControlAuditEventType,
    GlobalControlAuditRecord,
    audit_event_type_for,
)
from .decision import GlobalControlDecision
from .policy import GlobalControlPolicy
from .state import GlobalControlState


class GlobalControlController:

    def __init__(
        self,
        policy: GlobalControlPolicy | None = None,
    ) -> None:

        self.policy = (
            policy
            or GlobalControlPolicy()
        )

        self._state = (
            GlobalControlState.NORMAL
        )

        self._audit_trail: list[
            GlobalControlAuditRecord
        ] = []

        self._on_transition: (
            Callable[[GlobalControlAuditRecord], None]
            | None
        ) = None

    @property
    def state(self) -> GlobalControlState:
        return self._state

    @property
    def audit_trail(
        self,
    ) -> list[GlobalControlAuditRecord]:
        return list(self._audit_trail)

    def set_transition_hook(
        self,
        hook: Callable[[GlobalControlAuditRecord], None],
    ) -> None:
        """Register a callback invoked on every state transition."""
        self._on_transition = hook

    def set_state(
        self,
        state: GlobalControlState,
        *,
        incident_id: UUID | None = None,
        control_id: UUID | None = None,
        actor: str = "global-controller",
        reason: str = "",
        system_state: str = "",
    ) -> None:

        if state is self._state:
            return

        previous_state = self._state
        self._state = state

        record = GlobalControlAuditRecord(
            event_type=audit_event_type_for(
                previous_state,
                state,
            ),
            previous_state=previous_state,
            new_state=state,
            incident_id=incident_id,
            control_id=control_id,
            actor=actor,
            reason=reason,
            system_state=system_state,
        )
        self._audit_trail.append(record)

        if self._on_transition is not None:
            self._on_transition(record)

    def evaluate(self) -> GlobalControlDecision:

        if self._state == GlobalControlState.NORMAL:

            return GlobalControlDecision(
                state=self._state,
                allow_new_risk=True,
                allow_new_orders=True,
                allow_cancel_orders=True,
                allow_reduce_orders=True,
                allow_emergency_flatten=True,
                allow_recovery=False,
                reason="global_normal",
            )

        if self._state == GlobalControlState.RESTRICTED:

            return GlobalControlDecision(
                state=self._state,
                allow_new_risk=False,
                allow_new_orders=False,
                allow_cancel_orders=True,
                allow_reduce_orders=True,
                allow_emergency_flatten=True,
                allow_recovery=False,
                reason="global_restricted",
            )

        if self._state == GlobalControlState.KILLED:

            return GlobalControlDecision(
                state=self._state,
                allow_new_risk=False,
                allow_new_orders=False,
                allow_cancel_orders=(
                    self.policy.killed_allow_cancel
                ),
                allow_reduce_orders=(
                    self.policy.killed_allow_reduce
                ),
                allow_emergency_flatten=(
                    self.policy
                    .killed_allow_emergency_flatten
                ),
                allow_recovery=True,
                reason="global_killed",
            )

        if self._state == GlobalControlState.RECOVERY:

            return GlobalControlDecision(
                state=self._state,
                allow_new_risk=False,
                allow_new_orders=False,
                allow_cancel_orders=True,
                allow_reduce_orders=True,
                allow_emergency_flatten=True,
                allow_recovery=True,
                reason="global_recovery",
            )

        return GlobalControlDecision(
            state=self._state,
            allow_new_risk=False,
            allow_new_orders=False,
            allow_cancel_orders=False,
            allow_reduce_orders=False,
            allow_emergency_flatten=False,
            allow_recovery=False,
            reason="unknown_global_state",
        )
