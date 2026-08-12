"""Recovery controller (Commit 26 Part 1.5, spec sections 18-19, 29, 32-33).

完整恢复流程：

    KILLED
      ↓
    VALIDATING ──FAIL──► BLOCKED
      │
      └────PASS────► APPROVAL_REQUIRED ──APPROVE──► APPROVED
                                                      │
                                                      ▼
                                                  RESUMING ──► COMPLETED

关键原则：
- Recovery 必须经过 Validation 与 Manual Approval，才允许重新开放交易
  （spec section 19）。
- Recovery Start 具备唯一 recovery_id，且状态机只允许合法迁移
  （spec section 32-33）。
- 非法迁移（例如 NORMAL -> COMPLETED、KILLED -> NORMAL）会被拒绝。
"""

from __future__ import annotations

from uuid import UUID, uuid4

from .audit import (
    RecoveryAuditEventType,
    RecoveryAuditRecord,
)
from .decision import RecoveryDecision
from .gate import RecoveryChecks, RecoveryGate
from .policy import RecoveryPolicy
from .state import RecoveryState


class RecoveryTransitionError(RuntimeError):

    """Raised when a recovery state transition is illegal (spec section 33)."""


class RecoveryController:

    def __init__(
        self,
        policy: RecoveryPolicy | None = None,
        require_manual_approval: bool = True,
    ) -> None:

        if policy is not None:
            self.policy = policy
        else:
            self.policy = RecoveryPolicy(
                require_manual_approval=require_manual_approval,
            )

        self._gate = RecoveryGate(self.policy)

        self._state = RecoveryState.IDLE

        self._recovery_id: UUID | None = None

        self._audit_trail: list[RecoveryAuditRecord] = []

    @property
    def state(self) -> RecoveryState:
        return self._state

    @property
    def recovery_id(self) -> UUID | None:
        return self._recovery_id

    @property
    def audit_trail(self) -> list[RecoveryAuditRecord]:
        return list(self._audit_trail)

    @property
    def allow_resume(self) -> bool:
        # 只有 APPROVED 才允许恢复交易。
        return self._state is RecoveryState.APPROVED

    def evaluate(self) -> RecoveryDecision:
        return RecoveryDecision(
            state=self._state,
            allow_resume=self.allow_resume,
            reason=f"recovery_{self._state.value.lower()}",
        )

    # ------------------------------------------------------------------
    # State machine operations
    # ------------------------------------------------------------------

    def start(
        self,
        *,
        incident_id: UUID | str | None = None,
        control_id: UUID | str | None = None,
        actor: str = "recovery-orchestrator",
        reason: str = "recovery session started",
    ) -> UUID:

        if self._state in {
            RecoveryState.VALIDATING,
            RecoveryState.APPROVAL_REQUIRED,
            RecoveryState.APPROVED,
            RecoveryState.RESUMING,
        }:
            raise RecoveryTransitionError(
                f"cannot start a new recovery while in "
                f"{self._state.value}",
            )

        # 每次 Recovery Start 都具备唯一 recovery_id（spec section 32）。
        self._recovery_id = uuid4()

        self._record(
            RecoveryAuditEventType.RECOVERY_VALIDATION_STARTED,
            previous_state=self._state,
            new_state=RecoveryState.VALIDATING,
            incident_id=incident_id,
            control_id=control_id,
            actor=actor,
            reason=reason,
        )
        self._state = RecoveryState.VALIDATING

        return self._recovery_id

    def validate(
        self,
        checks: RecoveryChecks | None = None,
        *,
        incident_id: UUID | str | None = None,
        control_id: UUID | str | None = None,
        actor: str = "recovery-controller",
        reason: str = "",
    ) -> bool:

        if self._state is RecoveryState.IDLE:
            self.start(
                incident_id=incident_id,
                control_id=control_id,
                actor=actor,
                reason=reason or "auto-started validation",
            )
        elif self._state is RecoveryState.BLOCKED:
            # 修复后允许重新验证
            self._record(
                RecoveryAuditEventType.RECOVERY_VALIDATION_STARTED,
                previous_state=self._state,
                new_state=RecoveryState.VALIDATING,
                incident_id=incident_id,
                control_id=control_id,
                actor=actor,
                reason=reason or "re-validation started",
            )
            self._state = RecoveryState.VALIDATING
        elif self._state is not RecoveryState.VALIDATING:
            raise RecoveryTransitionError(
                f"cannot validate recovery in "
                f"{self._state.value}",
            )

        if checks is None:
            self._record(
                RecoveryAuditEventType.RECOVERY_VALIDATION_FAILED,
                previous_state=self._state,
                new_state=RecoveryState.BLOCKED,
                incident_id=incident_id,
                control_id=control_id,
                actor=actor,
                reason=reason or "no checks provided",
            )
            self._state = RecoveryState.BLOCKED
            return False

        if not self._gate.validate(checks):
            self._record(
                RecoveryAuditEventType.RECOVERY_VALIDATION_FAILED,
                previous_state=self._state,
                new_state=RecoveryState.BLOCKED,
                incident_id=incident_id,
                control_id=control_id,
                actor=actor,
                reason=reason or "recovery validation failed",
            )
            self._state = RecoveryState.BLOCKED
            return False

        if self.policy.require_manual_approval:
            self._record(
                RecoveryAuditEventType.RECOVERY_VALIDATION_PASSED,
                previous_state=self._state,
                new_state=RecoveryState.APPROVAL_REQUIRED,
                incident_id=incident_id,
                control_id=control_id,
                actor=actor,
                reason=reason or "recovery validation passed",
            )
            self._record(
                RecoveryAuditEventType.RECOVERY_APPROVAL_REQUIRED,
                previous_state=RecoveryState.VALIDATING,
                new_state=RecoveryState.APPROVAL_REQUIRED,
                incident_id=incident_id,
                control_id=control_id,
                actor=actor,
                reason="manual approval required",
            )
            self._state = RecoveryState.APPROVAL_REQUIRED
        else:
            self._record(
                RecoveryAuditEventType.RECOVERY_VALIDATION_PASSED,
                previous_state=self._state,
                new_state=RecoveryState.APPROVED,
                incident_id=incident_id,
                control_id=control_id,
                actor=actor,
                reason=reason or "recovery validation passed",
            )
            self._record(
                RecoveryAuditEventType.RECOVERY_APPROVED,
                previous_state=RecoveryState.VALIDATING,
                new_state=RecoveryState.APPROVED,
                incident_id=incident_id,
                control_id=control_id,
                actor=actor,
                reason="auto-approved (no manual approval required)",
            )
            self._state = RecoveryState.APPROVED

        return True

    def approve(
        self,
        *,
        actor: str = "risk-manager",
        reason: str = "manual approval granted",
        incident_id: UUID | str | None = None,
        control_id: UUID | str | None = None,
    ) -> None:

        if self._state is RecoveryState.APPROVED:
            # 幂等：重复 APPROVE 不重复产生副作用。
            return

        if self._state is not RecoveryState.APPROVAL_REQUIRED:
            raise RecoveryTransitionError(
                f"cannot approve recovery in {self._state.value}",
            )

        self._record(
            RecoveryAuditEventType.RECOVERY_APPROVED,
            previous_state=self._state,
            new_state=RecoveryState.APPROVED,
            incident_id=incident_id,
            control_id=control_id,
            actor=actor,
            reason=reason,
        )
        self._state = RecoveryState.APPROVED

    def resume(
        self,
        *,
        actor: str = "recovery-orchestrator",
        reason: str = "hierarchical resume started",
        incident_id: UUID | str | None = None,
        control_id: UUID | str | None = None,
    ) -> None:

        if self._state is not RecoveryState.APPROVED:
            raise RecoveryTransitionError(
                f"cannot resume recovery from {self._state.value}",
            )

        self._record(
            RecoveryAuditEventType.RECOVERY_RESUME_STARTED,
            previous_state=self._state,
            new_state=RecoveryState.RESUMING,
            incident_id=incident_id,
            control_id=control_id,
            actor=actor,
            reason=reason,
        )
        self._state = RecoveryState.RESUMING

    def complete(
        self,
        *,
        actor: str = "recovery-orchestrator",
        reason: str = "recovery completed",
        incident_id: UUID | str | None = None,
        control_id: UUID | str | None = None,
    ) -> None:

        if self._state is not RecoveryState.RESUMING:
            raise RecoveryTransitionError(
                f"cannot complete recovery from {self._state.value}",
            )

        self._record(
            RecoveryAuditEventType.RECOVERY_COMPLETED,
            previous_state=self._state,
            new_state=RecoveryState.COMPLETED,
            incident_id=incident_id,
            control_id=control_id,
            actor=actor,
            reason=reason,
        )
        self._state = RecoveryState.COMPLETED

    def fail(
        self,
        *,
        actor: str = "recovery-orchestrator",
        reason: str = "recovery failed",
        incident_id: UUID | str | None = None,
        control_id: UUID | str | None = None,
    ) -> None:

        if self._state is not RecoveryState.RESUMING:
            raise RecoveryTransitionError(
                f"cannot fail recovery from {self._state.value}",
            )

        self._record(
            RecoveryAuditEventType.RECOVERY_FAILED,
            previous_state=self._state,
            new_state=RecoveryState.FAILED,
            incident_id=incident_id,
            control_id=control_id,
            actor=actor,
            reason=reason,
        )
        self._state = RecoveryState.FAILED

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _record(
        self,
        event_type: RecoveryAuditEventType,
        *,
        previous_state: RecoveryState,
        new_state: RecoveryState,
        incident_id: UUID | str | None,
        control_id: UUID | str | None,
        actor: str,
        reason: str,
    ) -> None:

        self._audit_trail.append(
            RecoveryAuditRecord(
                event_type=event_type,
                previous_state=previous_state,
                new_state=new_state,
                recovery_id=self._recovery_id,
                incident_id=(
                    incident_id
                    if incident_id is None
                    else UUID(str(incident_id))
                ),
                control_id=(
                    control_id
                    if control_id is None
                    else UUID(str(control_id))
                ),
                actor=actor,
                reason=reason,
            ),
        )
