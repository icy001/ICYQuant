"""
ICYQuant Production Control Plane (Commit 24 Part 1.1).

The Control Plane answers the production questions:

    * What state is the whole system in right now?
    * Which components are healthy?
    * Can we trade right now?
    * When must trading stop?
    * When can trading resume?

State model (4 layers):

    System State       INITIALIZING → STARTING → READY / DEGRADED / RECOVERING / HALTED / FAILED / MAINTENANCE
    Component State    STARTING / HEALTHY / DEGRADED / UNHEALTHY / RECOVERING / STOPPED / UNKNOWN
    Trading State      TRADING_DISABLED / TRADING_READY / TRADING_DEGRADED / TRADING_HALTED
    Operational State  NORMAL / DEGRADED / RECOVERY / HALT / MAINTENANCE / EMERGENCY

Everything is event-driven: evaluation produces a StateDecision, the decision
is emitted as STATE_CHANGED events, and the ControlPlaneSnapshot is a
projection that can always be rebuilt by replaying the event log.

Commit 29 Part 1.1 adds — Production Control Plane Foundation:
  - Control Command / Request models with three-layer IDs (Request -> Decision -> Command)
  - Command lifecycle (RECEIVED -> AUTHORIZING -> AUTHORIZED -> DISPATCHING -> EXECUTING -> SUCCEEDED)
  - Handler registry (duplicate registration rejected), dispatcher, executor boundary
  - Control target model with fail-closed target resolution
  - Idempotency with command-fingerprint conflict detection
  - Governance authorization boundary (ControlAuthorizer) and ControlPlane facade
  - Fail-closed error model (CommandNotFound / TargetNotFound / CommandConflict / ...)

Commit 29 Part 1.2 adds — Governed Command Authorization Pipeline:
  - ControlAuthorizationContext (flat, governance-friendly authorization context)
  - ALLOW / DENY / REQUIRE_APPROVAL decision model with AuthorizationGrant
  - GovernanceAuthorizer adapter into the governance engine
  - ControlPipeline (validate -> authorise -> approval gate -> dispatch -> execute)
  - WAITING_APPROVAL lifecycle state and approval-completed grant path
  - Executor guard: every execution needs a valid, unexpired, fingerprint-bound grant
  - ControlAuditLog events threaded by correlation_id (REQUESTED -> ... -> SUCCEEDED)

Commit 29 Part 1.3 adds - Durable Command Lifecycle & Execution State Machine:
  - Strict command state machine (StateTransitionEngine + ALLOWED_TRANSITIONS)
  - Durable CommandRecord / CommandStore with optimistic-concurrency CAS
  - ExecutionAttempt ledger with an explicit UNKNOWN execution state
  - ExecutionTimeout / RetryPolicy (UNKNOWN is never blind-retried by default)
  - ControlRecovery (reconcile-first recovery) and crash-recovery boundary
  - Error classification (ControlErrorCode) for incident management
  Note: the spec's execution.py / recovery.py ship as execution_attempt.py /
  recovery_engine.py to avoid shadowing the existing execution/ and recovery/ packages.

Commit 29 Part 1.4 adds - Command Idempotency & Replay Protection:
  - IdempotencyKey / IdempotencyRecord / InMemoryIdempotencyStore (atomic create)
  - Command fingerprint (canonical SHA-256) and DuplicateDetector
  - IdempotencyConflict vs Duplicate (same key + different fingerprint is never a duplicate)
  - IdempotencyService (replay -> idempotency -> fingerprint -> dedup -> governance -> execution)
  - ReplayProtector (replay window + completed-command replay policy)
  - ExecutionClaim / ExecutionClaimStore with lease heartbeat and fencing token
  - Executor ownership guard (can_execute) - Authorization + Ownership + Fingerprint
"""

from .commands import (
    EvaluateTradingState,
    EvaluateTradingStateResult,
    UpdateComponentState,
    UpdateComponentStateResult,
)
from .domain import (
    ComponentCriticality,
    ComponentInfo,
    ComponentRegistry,
    ComponentState,
    ComponentType,
    ControlPlaneSnapshot,
    ControlPolicy,
    GateDecision,
    OperationalState,
    PolicyContext,
    PolicyDecision,
    PolicyResult,
    RiskIntegrity,
    Severity,
    StateDecision,
    StateReasonCode,
    StateTransitionError,
    SystemState,
    SystemStateMachine,
    TradingGate,
    TradingGateResult,
    TradingPolicy,
    TradingState,
    TradingStateMachine,
    TradingStateTransitionError,
)
from .events import (
    ComponentStateChanged,
    SystemStateChanged,
    TradingStateChanged,
)
from .repositories import ControlPlaneRepository
from .services import ControlPlaneService

# Commit 29 Part 1.1 — Production Control Plane Foundation
from .command import ControlCommand, command_fingerprint
from .command_type import ControlCommandType
from .dispatcher import ControlDispatcher
from .errors import (
    AuthorizationExpired,
    CommandConflict,
    CommandNotFound,
    CommandRecordNotFound,
    ControlErrorCode,
    ControlExecutionError,
    ControlPlaneError,
    DuplicateCommand,
    IdempotencyConflict,
    InvalidControlRequest,
    InvalidControlState,
    ReplayRejected,
    TargetNotFound,
    TargetResponseTimeout,
    UnauthorizedControl,
    VersionConflict,
    classify_error,
)
from .executor import ControlExecutor
from .models import (
    ControlAuthorizer as _LegacyControlAuthorizer,
    ControlHandler,
    ControlPlane,
)
from .registry import ControlRegistry, IdempotencyRegistry
from .request import ControlRequest, validate_request
from .result import ControlResult
from .state import (
    CONTROL_STATE_TRANSITIONS,
    ControlState,
    is_valid_transition,
    validate_transition,
)
from .target import (
    DEFAULT_CONTROL_TARGETS,
    ControlTarget,
    StaticTargetResolver,
    TargetResolver,
)

# Commit 29 Part 1.2 — Governed Command Authorization Pipeline
from .audit import ControlAuditEvent, ControlAuditEventType, ControlAuditLog
from .authorizer import (
    AuthorizationDecision,
    AuthorizationEffect,
    AuthorizationGrant,
    ControlAuthorizer,
    GovernanceAuthorizer,
    GrantValidator,
)
from .context import ControlAuthorizationContext
from .pipeline import ControlPipeline
from .service import ControlService

# Commit 29 Part 1.3 - Durable Command Lifecycle & Execution State Machine
from .execution_attempt import ExecutionAttempt, ExecutionRunner, ExecutionState
from .lifecycle import CommandLifecycle
from .recovery_engine import (
    ControlRecovery,
    RecoverableControlHandler,
    RecoveryAction,
    RecoveryDecision,
)
from .store import CommandRecord, CommandStore, InMemoryCommandStore, StateTransition
from .timeout import ExecutionTimeout, RetryPolicy
from .transition import ALLOWED_TRANSITIONS, InvalidTransition, StateTransitionEngine

# Commit 29 Part 1.4 - Command Idempotency & Replay Protection
from .claim import ClaimResult, ExecutionClaim, ExecutionClaimStore
from .deduplication import DuplicateDetector, IdempotencyService, RetryMetadata
from .duplicate import IdempotencyResult
from .fingerprint import fingerprint_command
from .idempotency import IdempotencyKey
from .idempotency_store import (
    IdempotencyRecord,
    IdempotencyStore,
    InMemoryIdempotencyStore,
)
from .replay import ReplayDecision, ReplayPolicy, ReplayProtector

# Commit 29 Part 1.5 - Observability, Audit Trail & Operational Telemetry
from .alerts import (
    HIGH_RISK_ACTIONS,
    HIGH_RISK_STATES,
    Alert,
    AlertRule,
    AlertSeverity,
    ControlAlertEvaluator,
    DEFAULT_THRESHOLDS,
)
from .audit_event import (
    AuditEvent,
    AuditEventType,
    AuditIntegrityError,
    AuditTrail,
    calculate_event_hash,
    verify_audit_chain,
)
# Note: the spec's health.py ships as control_health.py - services/control_plane/health/
# already exists as the Commit 24 health sub-package (like execution_attempt.py).
from .control_health import (
    ControlPlaneHealth,
    DependencyHealth,
    DependencyProbe,
    HealthSnapshot,
    HealthStatus,
)
from .diagnostics import (
    REDACTED,
    SENSITIVE_FIELDS,
    ControlPlaneDiagnostics,
    DiagnosticsSnapshot,
    TimelineEntry,
    redact,
    redact_value,
)
from .event import ControlEvent, ControlEventType, InMemoryEventStore
from .event_sink import (
    EventPublishError,
    EventSink,
    InMemoryEventSink,
    OutboxEntry,
    OutboxPublisher,
    OutboxState,
    OutboxStore,
    PublishResult,
)
from .metrics import ControlMetrics, ControlMetricsSnapshot
from .observability import ControlPlaneObservability
from .telemetry import (
    ControlPlaneTelemetry,
    OperationalSnapshot,
    RetryStormDetector,
)
from .tracing import ControlTrace, TraceSpan

__all__ = [
    "ComponentCriticality",
    "ComponentInfo",
    "ComponentRegistry",
    "ComponentState",
    "ComponentStateChanged",
    "ComponentType",
    "ControlPlaneRepository",
    "ControlPlaneService",
    "ControlPlaneSnapshot",
    "ControlPolicy",
    "EvaluateTradingState",
    "EvaluateTradingStateResult",
    "GateDecision",
    "OperationalState",
    "PolicyContext",
    "PolicyDecision",
    "PolicyResult",
    "RiskIntegrity",
    "Severity",
    "StateDecision",
    "StateReasonCode",
    "StateTransitionError",
    "SystemState",
    "SystemStateChanged",
    "SystemStateMachine",
    "TradingGate",
    "TradingGateResult",
    "TradingPolicy",
    "TradingState",
    "TradingStateChanged",
    "TradingStateMachine",
    "TradingStateTransitionError",
    "UpdateComponentState",
    "UpdateComponentStateResult",
    # Commit 29 Part 1.1 — Production Control Plane Foundation
    "CONTROL_STATE_TRANSITIONS",
    "CommandConflict",
    "CommandNotFound",
    "ControlAuthorizer",
    "ControlCommand",
    "ControlCommandType",
    "ControlDispatcher",
    "ControlExecutionError",
    "ControlExecutor",
    "ControlHandler",
    "ControlPlane",
    "ControlPlaneError",
    "ControlRegistry",
    "ControlRequest",
    "ControlResult",
    "ControlState",
    "ControlTarget",
    "DEFAULT_CONTROL_TARGETS",
    "IdempotencyRegistry",
    "InvalidControlRequest",
    "InvalidControlState",
    "StaticTargetResolver",
    "TargetNotFound",
    "TargetResolver",
    "UnauthorizedControl",
    "AuthorizationExpired",
    "command_fingerprint",
    "is_valid_transition",
    "validate_request",
    "validate_transition",
    # Commit 29 Part 1.2 - Governed Command Authorization Pipeline
    "AuthorizationDecision",
    "AuthorizationEffect",
    "AuthorizationGrant",
    "ControlAuditEvent",
    "ControlAuditEventType",
    "ControlAuditLog",
    "ControlAuthorizationContext",
    "ControlPipeline",
    "ControlService",
    "GovernanceAuthorizer",
    "GrantValidator",
    # Commit 29 Part 1.3 - Durable Command Lifecycle & Execution State Machine
    "ALLOWED_TRANSITIONS",
    "CommandLifecycle",
    "CommandRecord",
    "CommandRecordNotFound",
    "CommandStore",
    "ControlErrorCode",
    "ControlRecovery",
    "DuplicateCommand",
    "ExecutionAttempt",
    "ExecutionRunner",
    "ExecutionState",
    "ExecutionTimeout",
    "InMemoryCommandStore",
    "InvalidTransition",
    "RecoverableControlHandler",
    "RecoveryAction",
    "RecoveryDecision",
    "RetryPolicy",
    "StateTransition",
    "StateTransitionEngine",
    "TargetResponseTimeout",
    "VersionConflict",
    "classify_error",
    # Commit 29 Part 1.4 - Command Idempotency & Replay Protection
    "ClaimResult",
    "DuplicateDetector",
    "ExecutionClaim",
    "ExecutionClaimStore",
    "IdempotencyConflict",
    "IdempotencyKey",
    "IdempotencyRecord",
    "IdempotencyResult",
    "IdempotencyService",
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
    "ReplayDecision",
    "ReplayPolicy",
    "ReplayProtector",
    "ReplayRejected",
    "RetryMetadata",
    "fingerprint_command",
    # Commit 29 Part 1.5 - Observability, Audit Trail & Operational Telemetry
    "Alert",
    "AlertRule",
    "AlertSeverity",
    "AuditEvent",
    "AuditEventType",
    "AuditIntegrityError",
    "AuditTrail",
    "ControlAlertEvaluator",
    "ControlEvent",
    "ControlEventType",
    "ControlMetrics",
    "ControlMetricsSnapshot",
    "ControlPlaneDiagnostics",
    "ControlPlaneHealth",
    "ControlPlaneObservability",
    "ControlPlaneTelemetry",
    "ControlTrace",
    "DEFAULT_THRESHOLDS",
    "DependencyHealth",
    "DependencyProbe",
    "DiagnosticsSnapshot",
    "EventPublishError",
    "EventSink",
    "HealthSnapshot",
    "HealthStatus",
    "HIGH_RISK_ACTIONS",
    "HIGH_RISK_STATES",
    "InMemoryEventSink",
    "InMemoryEventStore",
    "OperationalSnapshot",
    "OutboxEntry",
    "OutboxPublisher",
    "OutboxState",
    "OutboxStore",
    "PublishResult",
    "REDACTED",
    "RetryStormDetector",
    "SENSITIVE_FIELDS",
    "TimelineEntry",
    "TraceSpan",
    "calculate_event_hash",
    "redact",
    "redact_value",
    "verify_audit_chain",
]
