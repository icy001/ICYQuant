"""Order Lifecycle Engine — Event-driven order lifecycle management.

The Lifecycle Engine is the core driver of OMS, providing:

- Event-driven state machine for order lifecycle transitions
- Duplicate event detection and sequence validation
- Event Sourcing + Snapshot recovery
- Fill processing with partial fill accumulation
- Replace / Cancel / Reject / Expire / Suspend handling
- Lifecycle audit trail

Architecture:
    Order Intent → Lifecycle Engine → Transition Engine → Event Store
    → Snapshot → Execution

Key components:
    LifecycleEngine: Unified entry point for lifecycle operations
    TransitionEngine: Validates and executes state transitions
    StateTransitionValidator: Enforces legal transition rules
    DuplicateEventDetector: Prevents duplicate event processing
    EventSequenceChecker: Validates event ordering and detects gaps
    LifecycleEventStore: Event-sourced persistence layer
    LifecycleSnapshot: State snapshot and recovery
    LifecycleAudit: Full audit trail
"""

from .lifecycle_engine import LifecycleEngine
from .lifecycle_runtime import LifecycleRuntime
from .lifecycle_manager import LifecycleManager
from .transition_engine import TransitionEngine, TransitionResult, TransitionEvent
from .state_transition_validator import StateTransitionValidator
from .lifecycle_dispatcher import LifecycleDispatcher, LifecycleEvent, LifecycleEventType
from .order_validator import OrderValidator, ValidationResult
from .order_router import OrderRouter, RouteResult
from .order_dispatcher import OrderDispatcher, DispatchResult
from .order_ack_handler import OrderAckHandler
from .pending_handler import PendingHandler
from .working_handler import WorkingHandler
from .partial_fill_handler import PartialFillHandler
from .fill_handler import FillHandler, FillResult
from .replace_handler import ReplaceHandler, ReplaceResult
from .cancel_handler import CancelHandler, CancelResult
from .reject_handler import RejectHandler, RejectResult
from .expire_handler import ExpireHandler
from .suspend_handler import SuspendHandler
from .recovery_handler import RecoveryHandler, RecoveryResult
from .duplicate_event_detector import DuplicateEventDetector
from .event_sequence_checker import EventSequenceChecker, SequenceResult
from .lifecycle_event_store import LifecycleEventStore, StoredEvent
from .lifecycle_snapshot import LifecycleSnapshot, SnapshotManager
from .lifecycle_audit import LifecycleAudit, AuditEntry
from .metrics import LifecycleMetrics
from .telemetry import LifecycleTelemetry
from .diagnostics import LifecycleDiagnostics
from .health import LifecycleHealth

__all__ = [
    "LifecycleEngine",
    "LifecycleRuntime",
    "LifecycleManager",
    "TransitionEngine",
    "TransitionResult",
    "TransitionEvent",
    "StateTransitionValidator",
    "LifecycleDispatcher",
    "LifecycleEvent",
    "LifecycleEventType",
    "OrderValidator",
    "ValidationResult",
    "OrderRouter",
    "RouteResult",
    "OrderDispatcher",
    "DispatchResult",
    "OrderAckHandler",
    "PendingHandler",
    "WorkingHandler",
    "PartialFillHandler",
    "FillHandler",
    "FillResult",
    "ReplaceHandler",
    "ReplaceResult",
    "CancelHandler",
    "CancelResult",
    "RejectHandler",
    "RejectResult",
    "ExpireHandler",
    "SuspendHandler",
    "RecoveryHandler",
    "RecoveryResult",
    "DuplicateEventDetector",
    "EventSequenceChecker",
    "SequenceResult",
    "LifecycleEventStore",
    "StoredEvent",
    "LifecycleSnapshot",
    "SnapshotManager",
    "LifecycleAudit",
    "AuditEntry",
    "LifecycleMetrics",
    "LifecycleTelemetry",
    "LifecycleDiagnostics",
    "LifecycleHealth",
]
