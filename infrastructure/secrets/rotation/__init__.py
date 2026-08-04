"""
Rotation subpackage for secret lifecycle management.

Provides production-grade secret rotation
capabilities including automatic scheduling,
dual-key transitions, approval workflows,
and comprehensive audit support.

Architecture:
    SecretRotationManager (main entry)
          |
    +---> RotationScheduler (timing)
    +---> RotationWorkflow (pipeline)
    |       +---> RotationValidator (pre-check)
    |       +---> DualKeyTransition (zero-downtime)
    |       +---> RotationRollback (recovery)
    +---> RotationApproval (human-in-the-loop)
    +---> RotationNotifier (event dispatch)
    +---> RotationAudit (compliance)

Usage:
    from infrastructure.secrets.rotation import SecretRotationManager

    manager = SecretRotationManager(provider=my_provider)
    result = await manager.rotate("database/password")
"""

from __future__ import annotations

from .policy import RotationPolicy, RotationPolicyRegistry
from .validator import RotationValidator, RotationCheckResult
from .approval import (
    ApprovalRequest,
    ApprovalResult,
    RotationApproval,
)
from .transition import DualKeyTransition, TransitionPhase
from .workflow import RotationWorkflow, WorkflowStep, WorkflowStatus
from .rollback import RotationRollback
from .executor import ExecutionResult, RotationExecutor
from .manager import SecretRotationManager
from .scheduler import RotationScheduler
from .notifier import (
    RotationNotifier,
    RotationEvent,
    RotationEventType,
)
from .audit import RotationAudit, RotationAuditEntry
from .metrics import RotationMetrics

__all__ = [
    # Manager
    "SecretRotationManager",
    # Scheduler
    "RotationScheduler",
    # Workflow
    "RotationWorkflow",
    "WorkflowStep",
    "WorkflowStatus",
    # Transition
    "DualKeyTransition",
    "TransitionPhase",
    # Policy
    "RotationPolicy",
    "RotationPolicyRegistry",
    # Validation
    "RotationValidator",
    "RotationCheckResult",
    # Approval
    "ApprovalRequest",
    "ApprovalResult",
    "RotationApproval",
    # Rollback
    "RotationRollback",
    # Executor
    "ExecutionResult",
    "RotationExecutor",
    # Notifier
    "RotationNotifier",
    "RotationEvent",
    "RotationEventType",
    # Audit
    "RotationAudit",
    "RotationAuditEntry",
    # Metrics
    "RotationMetrics",
]
