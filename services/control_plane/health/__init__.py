"""
Health / Heartbeat / Liveness (Commit 24 Part 1.2).

Three-layer model:

    Health
      ├── Liveness   ("is the process alive?")
      └── Readiness  ("is it ready to do work?")

Health monitoring is *passive* (heartbeats) + *active* (health probes),
and is evaluated by :class:`HealthEvaluator` into a HealthStatus and a
weighted health score.
"""

from .health_check import (
    HealthCheck,
    HealthCheckResult,
    HealthProbe,
    run_active_checks,
    run_health_check,
)
from .health_evaluator import (
    WEIGHT_DEPENDENCIES,
    WEIGHT_HEARTBEAT,
    WEIGHT_LIVENESS,
    WEIGHT_READINESS,
    HealthEvaluation,
    HealthEvaluator,
)
from .health_incident import (
    HealthIncident,
    HealthIncidentState,
    HealthIncidentTransitionError,
    incident_severity_for_criticality,
)
from .health_profile import HealthProfile
from .health_status import HealthStatus, combine_statuses, worse_status
from .heartbeat import Heartbeat, HeartbeatStatus
from .liveness import (
    FunctionLivenessProbe,
    HeartbeatLivenessProbe,
    LivenessEvaluation,
    LivenessProbe,
    LivenessStatus,
    StaticLivenessProbe,
)
from .readiness import (
    DataFreshness,
    DependencyStatus,
    FreshnessPolicy,
    ReadinessEvaluation,
    ReadinessStatus,
    evaluate_readiness,
)

__all__ = [
    "DataFreshness",
    "DependencyStatus",
    "FreshnessPolicy",
    "FunctionLivenessProbe",
    "HealthCheck",
    "HealthCheckResult",
    "HealthEvaluation",
    "HealthEvaluator",
    "HealthIncident",
    "HealthIncidentState",
    "HealthIncidentTransitionError",
    "HealthProbe",
    "HealthProfile",
    "HealthStatus",
    "Heartbeat",
    "HeartbeatLivenessProbe",
    "HeartbeatStatus",
    "LivenessEvaluation",
    "LivenessProbe",
    "LivenessStatus",
    "ReadinessEvaluation",
    "ReadinessStatus",
    "StaticLivenessProbe",
    "WEIGHT_DEPENDENCIES",
    "WEIGHT_HEARTBEAT",
    "WEIGHT_LIVENESS",
    "WEIGHT_READINESS",
    "combine_statuses",
    "evaluate_readiness",
    "incident_severity_for_criticality",
    "run_active_checks",
    "run_health_check",
    "worse_status",
]
