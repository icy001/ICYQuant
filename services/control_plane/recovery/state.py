"""Recovery gate state machine (Commit 26 Part 1.5, spec section 12).

注意：这是 Part 1.5 引入的"恢复门控"状态机，用于 Global Kill 之后的
Validation -> Approval -> Resume 流程。它与 Commit 24 的
``recovery.recovery_state.RecoveryState``（Detect/Isolate/Recover 编排
状态机）是两个不同的概念。
"""

from enum import Enum


class RecoveryState(str, Enum):

    IDLE = "IDLE"

    VALIDATING = "VALIDATING"

    BLOCKED = "BLOCKED"

    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"

    APPROVED = "APPROVED"

    RESUMING = "RESUMING"

    COMPLETED = "COMPLETED"

    FAILED = "FAILED"
