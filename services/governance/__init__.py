"""
ICYQuant Institutional Decision & Governance Layer
Commit 20 Part 1.1 — Decision Governance Foundation
Commit 20 Part 1.2 — Versioned Policy & Rule Engine
Commit 20 Part 1.3 — Approval / Delegation / Authority Workflow
Commit 20 Part 1.4 — Governance Audit & Decision Lineage
Commit 20 Part 1.5 — Autonomous Governance Control Plane

Provides:
  - Governance Engine: centralized decision authorization
  - Policy Engine: institutional policy evaluation (simple + versioned)
  - Authority Engine: actor-based permission management
  - Constraint Engine: capital/risk/leverage/liquidity/concentration/survival limits
  - Approval Engine: multi-level review workflows
  - Decision Guard: final gate before execution
  - Audit Trail: full institutional decision records

Part 1.5 adds:
  - Autonomous Control Plane with continuous control loop
  - Governance state machine (NORMAL → WATCH → RESTRICTED → FROZEN → EMERGENCY → RECOVERY)
  - Five guardians: risk, authority, approval, policy, execution
  - Emergency controller with policy-constrained authority
  - Freeze / Exposure / Revoke / Escalation controllers
  - Structured intervention plans with verification
  - Watchdog for governance system health monitoring
  - Fail-closed principle for critical governance failures

Commit 28 Part 1.1 adds:
  - Production Governance Layer (Identity / Role / Permission / Policy)
  - Governance Context, Decision (ALLOW / DENY / REQUIRE_APPROVAL)
  - Governance Approval and immutable Governance Audit Evidence
  - In-memory Governance Registry with standard roles, permissions, policies
  - Default Deny / Fail Closed / Least Privilege / Separation of Duties
"""

__version__ = "0.4.0"

# Commit 28 Part 1.1 — Production Governance Layer
from .approval import Approval, ApprovalState
from .audit import GovernanceAuditEvent
from .decision import (
    DecisionEffect,
    GovernanceContext,
    GovernanceDecision,
    GovernanceEngine,
)
from .models import Principal
from .permission import Permission, build_standard_permissions
from .policy import Policy
from .registry import (
    GovernanceRegistry,
    build_standard_governance,
    build_standard_policies,
    register_standard_governance,
)
from .role import Role, build_standard_roles

# Commit 28 Part 1.2 — Deterministic Policy Evaluation Engine
from .condition import ConditionEvaluator
from .resolver import PermissionResolver

# Commit 28 Part 1.3 — Four-Eyes Approval & Separation of Duties
from .approval import (
    ApprovalAggregator,
    ApprovalDecision,
    approve,
    consume,
    expire_approval,
    reject,
    validate_approver,
    validate_binding,
)
from .approval_engine import GovernanceApprovalEngine
from .approval_rule import ApprovalRule, is_eligible
from .audit import (
    ApprovalAuditEvent,
    ApprovalAuditEventType,
    ApprovalAuditStore,
)

# Commit 28 Part 1.4 — Approval Delegation, Quorum & Authority Boundary
from .authority import (
    Authority,
    AuthorityResolver,
    AuthoritySnapshot,
    AuthoritySource,
    RolePermissionView,
)
from .delegation import (
    AuthorityDelegation,
    DelegationAuthorityValidator,
    EmergencyDelegation,
    ScopedDelegationValidator,
    can_delegate,
)
from .quorum import QuorumEvaluator, QuorumRule


__all__ = [
    # Core
    "GovernanceEngine",
    "GovernanceRuntime",
    "GovernanceManager",
    "GovernanceController",
    "GovernanceOrchestrator",
    # Decision
    "DecisionGovernance",
    "DecisionContext",
    "DecisionRequest",
    "DecisionResult",
    "DecisionStatus",
    # Policy (simple)
    "PolicyEngine",
    "Policy",
    "PolicyRule",
    "PolicyCondition",
    "PolicyAction",
    "PolicyEvaluator",
    # Policy (versioned) — Part 1.2
    "PolicyVersion",
    "PolicyStatus",
    "PolicyLifecycleStatus",
    "PolicyStateMachine",
    "PolicyPriorityLevel",
    "PolicyMetadata",
    "PolicyReviewRecord",
    "PolicyScopeConstants",
    "ScopeHierarchy",
    "PolicyScope",
    "PolicyRuleSet",
    "RuleSetEvaluationMode",
    "RuleSetStatus",
    "RuleEvaluation",
    "RuleSetResult",
    "PolicyExpression",
    "ExpressionType",
    "ExpressionBuilder",
    "LogicalOperator",
    "ArithmeticOperator",
    "AggregationFunction",
    "PolicyEffect",
    "EffectType",
    "EffectSeverity",
    "AggregatedEffects",
    "PolicyEvaluationContext",
    "PolicyOutcome",
    "VersionedPolicyResult",
    "EvaluationTrace",
    "PolicyOverride",
    "OverrideType",
    "OverrideStatus",
    "OverrideRegistry",
    "PolicyException",
    "PolicyDependency",
    "DependencyType",
    "DependencyGraph",
    "PolicyRegistry",
    "PolicyRepository",
    "PolicyRepositoryBackend",
    "InMemoryRepositoryBackend",
    "PolicyLoader",
    "PolicyPublisher",
    "PublishResult",
    "PolicyActivator",
    "ActivationResult",
    "PolicyVersionManager",
    "VersionDiff",
    "PolicyValidator",
    "ValidationResult",
    "PolicyConflictDetector",
    "PolicyConflict",
    "ConflictType",
    "ConflictSeverity",
    "PolicyCache",
    "CacheEntry",
    # Authority
    "AuthorityEngine",
    "AuthorityPolicy",
    "DecisionAuthority",
    "ApprovalRequirement",
    # Constraints
    "GovernanceConstraint",
    "CapitalConstraint",
    "RiskConstraint",
    "LeverageConstraint",
    "LiquidityConstraint",
    "ConcentrationConstraint",
    "AutonomyConstraint",
    # Approval
    "ApprovalEngine",
    "ApprovalRequest",
    "ApprovalResult",
    "ApprovalWorkflow",
    # Guards
    "DecisionGuard",
    "PolicyGuard",
    "AuthorityGuard",
    "AutonomyGuard",
    # Audit (Part 1.1)
    "DecisionAudit",
    "GovernanceAudit",
    "PolicyAudit",
    "ApprovalAudit",
    # Audit (Part 1.4) — Immutable audit system
    "AuditEngine",
    "AuditEvent",
    "AuditEventType",
    "AuditActor",
    "ActorType",
    "AuditAction",
    "AuditOutcome",
    "AuditContext",
    "ImmutableAuditLog",
    "AuditHash",
    "AuditChain",
    "ChainLink",
    "AuditIntegrityChecker",
    "ExecutionAudit",
    "ExecutionStatus",
    "AuditMetrics",
    # Lineage (Part 1.4) — Decision lineage graph
    "LineageEngine",
    "LineageNode",
    "LineageNodeType",
    "LineageEdge",
    "LineageEdgeType",
    "LineageGraph",
    "LineageQuery",
    "QueryDirection",
    "LineageSnapshot",
    "LineageResolver",
    "LineageExporter",
    "LineageReconstructor",
    "LineageValidator",
    # Decision Record (Part 1.4)
    "DecisionRecord",
    "DecisionRecordStatus",
    "DecisionSnapshot",
    "DecisionTrace",
    "TraceStep",
    "TraceStepRecord",
    "DecisionReason",
    "ReasonType",
    "DecisionEvidence",
    "EvidenceItem",
    # Events
    "GovernanceEvent",
    "GovernanceEventType",
    "GovernanceEventStore",
    # Control Plane (Part 1.5) — Autonomous governance
    "GovernanceControlPlane",
    "ControlLoop",
    "LoopCycle",
    "LoopPhase",
    "GovernanceStateType",
    "GovernanceStateMachine",
    "GovernanceStateTransition",
    "ControlActionType",
    "ControlDecision",
    "ControlPolicy",
    "ControlCondition",
    "ControlTrigger",
    "TriggerType",
    "TriggerCategory",
    "Severity",
    # Monitor (Part 1.5)
    "GovernanceMonitor",
    "GovernanceSignal",
    "SignalType",
    "GovernanceDetector",
    "RiskDetector",
    "ExecutionDetector",
    "GovernanceThreshold",
    "GovernanceRuntimeState",
    # Guardians (Part 1.5)
    "RiskGuardian",
    "AuthorityGuardian",
    "ApprovalGuardian",
    "PolicyGuardian",
    "ExecutionGuardian",
    # Emergency (Part 1.5)
    "EmergencyController",
    "EmergencyPolicy",
    "EmergencyAction",
    "EmergencyActionType",
    "EmergencyState",
    "EmergencyStateType",
    # Controllers (Part 1.5)
    "FreezeController",
    "FreezeScope",
    "ExposureController",
    "RevokeController",
    "EscalationController",
    "EscalationLevel",
    # Intervention (Part 1.5)
    "GovernanceIntervention",
    "InterventionPlan",
    "InterventionStep",
    "InterventionStepType",
    "InterventionResult",
    # Watchdog / Health (Part 1.5)
    "GovernanceWatchdog",
    "GovernanceHeartbeat",
    # Metrics (Part 1.5)
    "ControlMetrics",
    # Approval (Part 1.3)
    "ApprovalManager",
    "ApprovalController",
    "ApprovalRepository",
    "ApprovalBackend",
    "InMemoryApprovalBackend",
    "ApprovalPolicy",
    "ApprovalLevel",
    "ApprovalThresholdRule",
    "ApprovalResponse",
    "ApproverEntry",
    "ApprovalThreshold",
    "ThresholdTier",
    "ThresholdResult",
    "ApprovalStep",
    "StepType",
    "StepStatus",
    "ApprovalStage",
    "StageType",
    "StageStatus",
    "ApprovalTransition",
    "ApprovalRouter",
    "ApproverTarget",
    "RouteResult",
    # Authority extended (Part 1.3)
    "AuthorityScope",
    "AuthorityScopeLevel",
    "AuthorityLimit",
    "AuthorityGrant",
    "AuthorityRevocation",
    "AuthorityRevocationRegistry",
    # Delegation (Part 1.3)
    "DelegationEngine",
    "Delegation",
    "DelegationScope",
    "DelegationLimit",
    "DelegationStatus",
    "DelegationValidator",
    "DelegationValidationResult",
    # Guards extended (Part 1.3)
    "ApprovalGuard",
    "ApprovalGuardCheckResult",
    "DelegationGuard",
    "DelegationGuardCheckResult",
    # Audit extended (Part 1.3)
    "AuthorityAuditRecord",
    "AuthorityAuditAction",
    "AuthorityAuditStore",
    "DelegationAuditRecord",
    "DelegationAuditAction",
    "DelegationAuditStore",
    # Metrics (Part 1.3)
    "ApprovalMetrics",
    "get_approval_metrics",
    # Diagnostics
    "GovernanceMetrics",
    "GovernanceTelemetry",
    "GovernanceDiagnostics",
    "GovernanceHealth",
    # Commit 28 Part 1.1 — Production Governance Layer
    "Approval",
    "ApprovalState",
    "DecisionEffect",
    "GovernanceAuditEvent",
    "GovernanceContext",
    "GovernanceDecision",
    "GovernanceRegistry",
    "Permission",
    "Principal",
    "Role",
    "build_standard_governance",
    "build_standard_permissions",
    "build_standard_policies",
    "build_standard_roles",
    "register_standard_governance",
    # Commit 28 Part 1.2 — Deterministic Policy Evaluation Engine
    "ConditionEvaluator",
    "PermissionResolver",
    # Commit 28 Part 1.3 — Four-Eyes Approval & Separation of Duties
    "ApprovalAggregator",
    "ApprovalAuditEvent",
    "ApprovalAuditEventType",
    "ApprovalAuditStore",
    "ApprovalDecision",
    "ApprovalRule",
    "GovernanceApprovalEngine",
    "approve",
    "consume",
    "expire_approval",
    "is_eligible",
    "reject",
    "validate_approver",
    "validate_binding",
    # Commit 28 Part 1.4 — Delegation, Quorum & Authority Boundary
    "Authority",
    "AuthorityDelegation",
    "AuthorityResolver",
    "AuthoritySnapshot",
    "AuthoritySource",
    "DelegationAuthorityValidator",
    "EmergencyDelegation",
    "QuorumEvaluator",
    "QuorumRule",
    "RolePermissionView",
    "ScopedDelegationValidator",
    "can_delegate",
]
