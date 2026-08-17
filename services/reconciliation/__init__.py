"""
ICYQuant Reconciliation Service.
"""

from .model import (
    DifferenceType,
    ReconciliationDifference,
)

from .engine import (
    ReconciliationEngine,
)

from .repair_actions import (
    RepairBuilder,
)

from .comparator import (
    PositionComparator,
    ExecutionPositionComparator,
)

from .repair_service import (
    RepairService,
)

from .conflict import (
    ConflictResolutionEngine,
)

from .policy import (
    DataSource,
    ResolutionAction,
    ResolutionPolicy,
)

# -------------------------------------------------------------------
# Reconciliation Difference Classification, Repair Planning,
# Repair Execution, Recovery Audit & Self-Healing Lifecycle
# (Commit 40 Part 1.2 / 1.3 / 1.4 / 1.5)
# -------------------------------------------------------------------

from .id_generator import IdGenerator
from .lifecycle import (
    InvalidLifecycleTransition,
    ReconciliationLifecycleManager,
)
from .models.execution_position import ExecutionPosition
from .models.recovery_result import RecoveryResult
from .models.repair import (
    RepairActionType,
    RepairAuditEventType,
    RepairPlan,
    RepairStatus,
)
from .models.repair_record import RepairRecord
from .models.repair_verification import RepairVerification
from .models.result import ReconciliationResult
from .models.snapshot import PositionSnapshot
from .models.status import (
    ReconciliationLifecycle,
    ReconciliationStatus,
)
from .planner import RepairPlanner
from .position_builder import ExecutionPositionBuilder
from .recovery_metrics import RecoveryMetrics
from .recovery_policy import RecoveryPolicy
from .recovery_service import (
    RecoveryOutcome,
    RecoveryService,
)
from .repair_executor import (
    RepairExecutor,
    RepairResult,
)
from .repair_repository import (
    InMemoryRepairRepository,
    RepairRepository,
)
from .safety_guard import (
    RecoverySafetyError,
    RecoverySafetyGuard,
)
from .self_healing import SelfHealingCoordinator
from .service import ReconciliationService
from .workflow import ReconciliationWorkflow


__all__ = [
    "DifferenceType",
    "ReconciliationDifference",
    "ReconciliationEngine",
    "RepairBuilder",
    "RepairService",
    "ConflictResolutionEngine",
    "DataSource",
    "ResolutionAction",
    "ResolutionPolicy",
    # ---- Commit 40 Part 1.2 / Part 1.3 / Part 1.4 / Part 1.5 ----
    "ExecutionPosition",
    "ExecutionPositionBuilder",
    "ExecutionPositionComparator",
    "IdGenerator",
    "InMemoryRepairRepository",
    "InvalidLifecycleTransition",
    "PositionSnapshot",
    "ReconciliationLifecycle",
    "ReconciliationLifecycleManager",
    "ReconciliationResult",
    "ReconciliationService",
    "ReconciliationStatus",
    "RecoveryMetrics",
    "RecoveryOutcome",
    "RecoveryPolicy",
    "RecoveryResult",
    "RecoverySafetyError",
    "RecoverySafetyGuard",
    "RecoveryService",
    "RepairActionType",
    "RepairAuditEventType",
    "RepairExecutor",
    "RepairPlan",
    "RepairPlanner",
    "RepairRecord",
    "RepairRepository",
    "RepairResult",
    "RepairStatus",
    "RepairVerification",
    "SelfHealingCoordinator",
    "ReconciliationWorkflow",
]