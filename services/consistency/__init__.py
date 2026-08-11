"""Consistency service — public API and exports."""

from .domain.consistency_check import (
    ConsistencyCheck,
    ExecutionFact,
    LedgerView,
    PositionView,
    ReconciliationTrigger,
)
from .domain.consistency_result import ConsistencyResult, CheckMatrix, MatrixRow
from .domain.consistency_status import (
    ConsistencyDomainStatus,
    ReconciliationTriggerPriority,
)
from .events.consistency_failed import ConsistencyFailed
from .events.consistency_restored import ConsistencyRestored
from .checks.execution_position_check import (
    ExecutionPositionCheck,
    check_execution_position,
)
from .checks.execution_ledger_check import (
    ExecutionLedgerCheck,
    check_execution_ledger,
)
from .checks.cross_domain_check import CrossDomainCheck
from .commands.run_consistency_check import (
    RunConsistencyCheck,
    run_consistency_check,
)
from .services.consistency_service import ConsistencyService

__all__ = [
    # Domain
    "ConsistencyCheck",
    "ExecutionFact",
    "PositionView",
    "LedgerView",
    "ReconciliationTrigger",
    "ConsistencyResult",
    "CheckMatrix",
    "MatrixRow",
    "ConsistencyDomainStatus",
    "ReconciliationTriggerPriority",
    # Events
    "ConsistencyFailed",
    "ConsistencyRestored",
    # Checks
    "ExecutionPositionCheck",
    "check_execution_position",
    "ExecutionLedgerCheck",
    "check_execution_ledger",
    "CrossDomainCheck",
    # Commands
    "RunConsistencyCheck",
    "run_consistency_check",
    # Service
    "ConsistencyService",
]
