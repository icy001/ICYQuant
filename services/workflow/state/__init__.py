"""Workflow state package — state machine, persistence, and recovery.

Provides:
  - Workflow & Node state machines with validated transitions
  - Checkpoint / Snapshot / WAL persistence
  - Execution journal for full audit & replay
  - Event store & event sourcing for state rebuild
  - Recovery engine with multiple recovery strategies
  - Consistency checker & diagnostics
  - Background scheduler & telemetry
"""

from .workflow_state import WorkflowExecutionStatus, WorkflowState, VALID_WORKFLOW_TRANSITIONS
from .node_state import NodeExecutionStatus, NodeState, VALID_NODE_TRANSITIONS
from .lifecycle import LifecycleManager
from .state_machine import WorkflowStateMachine
from .transition_manager import TransitionManager, TransitionRecord
from .state_validator import StateValidator
from .execution_guard import ExecutionGuard, ExecutionToken
from .idempotency import IdempotencyManager, IdempotencyKey, IdempotencyRecord
from .checkpoint_manager import CheckpointManager, Checkpoint
from .checkpoint_repository import CheckpointRepository
from .checkpoint_scheduler import CheckpointScheduler
from .snapshot_manager import SnapshotManager, Snapshot
from .wal import WAL, WALEntry, WALEntryType, WALEntryStatus
from .journal import Journal, JournalEntry, JournalEntryType
from .event_store import EventStore, StoredEvent, EventBackend
from .event_sourcing import EventSourcingEngine
from .replay_engine import ReplayEngine
from .recovery_engine import RecoveryEngine
from .recovery_planner import RecoveryPlanner, RecoveryStrategy
from .consistency_checker import ConsistencyChecker
from .persistence import PersistenceLayer
from .scheduler import BackgroundScheduler, ScheduledTask
from .metrics import StateMetricsCollector, MetricCounter, MetricGauge
from .telemetry import StateTelemetry
from .diagnostics import StateDiagnostics
from .health import StateHealthChecker

__all__ = [
    # State models
    "WorkflowExecutionStatus",
    "WorkflowState",
    "VALID_WORKFLOW_TRANSITIONS",
    "NodeExecutionStatus",
    "NodeState",
    "VALID_NODE_TRANSITIONS",
    # Core
    "LifecycleManager",
    "WorkflowStateMachine",
    "TransitionManager",
    "TransitionRecord",
    "StateValidator",
    "ExecutionGuard",
    "ExecutionToken",
    "IdempotencyManager",
    "IdempotencyKey",
    "IdempotencyRecord",
    # Persistence
    "CheckpointManager",
    "Checkpoint",
    "CheckpointRepository",
    "CheckpointScheduler",
    "SnapshotManager",
    "Snapshot",
    "WAL",
    "WALEntry",
    "WALEntryType",
    "WALEntryStatus",
    "Journal",
    "JournalEntry",
    "JournalEntryType",
    "PersistenceLayer",
    # Event & Recovery
    "EventStore",
    "StoredEvent",
    "EventBackend",
    "EventSourcingEngine",
    "ReplayEngine",
    "RecoveryEngine",
    "RecoveryPlanner",
    "RecoveryStrategy",
    "ConsistencyChecker",
    # Cross-cutting
    "BackgroundScheduler",
    "ScheduledTask",
    "StateMetricsCollector",
    "MetricCounter",
    "MetricGauge",
    "StateTelemetry",
    "StateDiagnostics",
    "StateHealthChecker",
]
