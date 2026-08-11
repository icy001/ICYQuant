"""
ICYQuant Autonomous Quant Control Plane

The Control Plane is the centralized governance layer that orchestrates
all autonomous domains (Research, Alpha, Strategy, Portfolio, Risk, Execution).

It provides:
- Policy Engine: unified policy enforcement across all domains
- Autonomy Engine: level-based autonomy control
- Decision Engine: centralized decision lifecycle
- Budget Manager: resource constraints for autonomous operations
- Model Lifecycle: promotion/demotion/quarantine/retirement
- Approval Engine: human override and approval gates
- Permission Engine: domain-specific RBAC integration
- Audit Engine: immutable decision logging
- Incident Manager: anomaly detection and recovery
- Circuit Breaker / Kill Switch: system-wide safety
- Health Monitoring: cross-domain health aggregation

Version: v0.4.0-alpha2
Commit: 18 Part 1.5
"""

__all__ = [
    # Core
    "ControlPlane",
    "ControlPlaneRuntime",
    "ControlPlaneManager",
    "ControlPlaneController",
    "ControlPlaneGateway",
    "ControlPlaneOrchestrator",

    # Decision
    "DecisionEngine",
    "DecisionContext",
    "DecisionRequest",
    "DecisionResult",
    "DecisionLineage",
    "DecisionRegistry",

    # Policy
    "PolicyEngine",
    "PolicyRegistry",
    "PolicyEvaluator",
    "PolicyVersion",
    "PolicyScope",
    "PolicyConflictResolver",

    # Autonomy
    "AutonomyEngine",
    "AutonomyLevel",
    "AutonomyPolicy",
    "AutonomyTransition",
    "AutonomyGuard",

    # Budget
    "ResearchBudgetManager",
    "ComputeBudgetManager",
    "ExperimentBudgetManager",
    "StrategyBudgetManager",
    "ExecutionBudgetManager",

    # Model Lifecycle
    "ModelLifecycle",
    "ModelRegistry",
    "ModelVersion",
    "ModelState",
    "ModelHealth",
    "ModelDecayDetector",
    "ModelDegradationDetector",
    "ModelRetirement",

    # Promotion
    "PromotionEngine",
    "PromotionPolicy",
    "PromotionGate",
    "DemotionEngine",
    "RollbackEngine",
    "QuarantineEngine",

    # Approval
    "ApprovalEngine",
    "ApprovalPolicy",
    "ApprovalRequest",
    "ApprovalGate",
    "HumanOverride",

    # Permission
    "PermissionEngine",
    "ResearchPermissions",
    "StrategyPermissions",
    "PortfolioPermissions",
    "RiskPermissions",
    "ExecutionPermissions",
    "ProductionPermissions",

    # Audit
    "AuditEngine",
    "AuditEvent",
    "AuditLog",
    "ImmutableDecisionLog",
    "LineageAudit",

    # Incident
    "IncidentManager",
    "AnomalyController",
    "CircuitBreaker",
    "GlobalKillSwitch",
    "RecoveryController",

    # Health
    "SystemHealth",
    "AutonomyHealth",
    "ResearchHealth",
    "StrategyHealth",
    "PortfolioHealth",
    "RiskHealth",
    "ExecutionHealth",

    # Memory
    "ControlPlaneMemory",
    "PolicyMemory",
    "DecisionMemory",
    "IncidentMemory",

    # Observability
    "Metrics",
    "Telemetry",
    "Diagnostics",
    "Health",
]
