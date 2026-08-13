"""Runbook & Operator Workflow (Commit 27 Part 1.5).

系统发生事故以后，Operator 不需要"凭经验处理"，而是按照确定性的
Runbook 执行:

    Incident
        ↓
    Runbook Selected
        ↓
    Triage -> Checklist -> Mitigation -> Approval -> Control
        ↓
    Recovery -> Validation -> Resume -> Close

核心边界（spec sections 10, 28-30）:

1. Runbook 不直接执行 Control：
   Runbook -> Action -> Control Request -> Authorization -> Control Plane。

2. 第一版执行器只负责 Step State，不直接执行危险操作。

3. 不允许"跳步骤后无记录"：SKIPPED 必须记录 reason / actor / timestamp。

4. 角色分离：Operator 执行标准 Runbook，Incident Commander / Control
   Operator 才能批准与执行 Kill / Pause / Failover。
"""

from .action import RunbookAction
from .approval import (
    ApprovalRequest,
    ApprovalWorkflow,
    requires_approval,
)
from .checklist import (
    Checklist,
    ChecklistItem,
)
from .condition import (
    ConditionOperator,
    RunbookCondition,
    evaluate_condition,
)
from .executor import (
    RunbookExecution,
    RunbookExecutor,
    StepExecutionRecord,
    StepStatus,
)
from .models import (
    Runbook,
    RunbookSeverity,
)
from .recovery import (
    RECOVERY_CHECKLIST_ITEMS,
    RecoveryGate,
    build_recovery_checklist,
)
from .registry import (
    RunbookRegistry,
    build_standard_runbooks,
    register_standard_runbooks,
)
from .runbook import (
    RunbookDefinition,
    RunbookValidator,
)
from .step import (
    RunbookStep,
    StepType,
)

__all__ = [
    "ApprovalRequest",
    "ApprovalWorkflow",
    "Checklist",
    "ChecklistItem",
    "ConditionOperator",
    "RECOVERY_CHECKLIST_ITEMS",
    "RecoveryGate",
    "Runbook",
    "RunbookAction",
    "RunbookCondition",
    "RunbookDefinition",
    "RunbookExecution",
    "RunbookExecutor",
    "RunbookRegistry",
    "RunbookSeverity",
    "RunbookStep",
    "RunbookValidator",
    "StepExecutionRecord",
    "StepStatus",
    "StepType",
    "build_recovery_checklist",
    "build_standard_runbooks",
    "evaluate_condition",
    "register_standard_runbooks",
    "requires_approval",
]
