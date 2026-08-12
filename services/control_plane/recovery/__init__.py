"""
Recovery — autonomous recovery orchestration for the Control Plane.

The recovery package coordinates the Detect -> Isolate -> Recover -> Reconcile
-> Verify -> Ramp Up -> Resume pipeline.  It never mutates business state; it
produces requests for domain services and persists durable checkpoints so a
crashed orchestrator can resume instead of restarting.
"""

from .recovery_checkpoint import RecoveryCheckpoint, compute_checksum
from .recovery_context import RecoveryContext, RecoveryScope
from .recovery_orchestrator import (
    InMemoryEventBus,
    RecoveryNotFoundError,
    RecoveryOrchestrator,
    RecoverySession,
    RetryPolicy,
)
from .recovery_plan import RecoveryPlan
from .recovery_result import RampUpLevel, RecoveryResult, VerificationStatus
from .recovery_state import (
    FailureClass,
    RecoveryState,
    RecoveryStateMachine,
    classify_failure,
)
from .recovery_step import (
    RecoveryAction,
    RecoveryStep,
    StepOutcome,
    StepStatus,
    StepType,
    make_step,
)
from .recovery_strategy import (
    STRATEGIES,
    EventRecoveryStrategy,
    GlobalRecoveryStrategy,
    LedgerRecoveryStrategy,
    PositionRecoveryStrategy,
    RecoveryStrategy,
    build_plan,
    get_strategy,
    strategy_for_trigger,
)

__all__ = [
    "RecoveryState",
    "RecoveryStateMachine",
    "FailureClass",
    "classify_failure",
    "RecoveryScope",
    "RecoveryContext",
    "StepType",
    "StepStatus",
    "RecoveryStep",
    "RecoveryAction",
    "StepOutcome",
    "make_step",
    "RecoveryPlan",
    "RecoveryCheckpoint",
    "compute_checksum",
    "VerificationStatus",
    "RampUpLevel",
    "RecoveryResult",
    "RecoveryStrategy",
    "PositionRecoveryStrategy",
    "LedgerRecoveryStrategy",
    "EventRecoveryStrategy",
    "GlobalRecoveryStrategy",
    "STRATEGIES",
    "get_strategy",
    "strategy_for_trigger",
    "build_plan",
    "RecoveryOrchestrator",
    "RecoverySession",
    "RecoveryNotFoundError",
    "RetryPolicy",
    "InMemoryEventBus",
]
