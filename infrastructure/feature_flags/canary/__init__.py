"""
Canary release platform.

Provides a complete canary deployment system
with multi-stage progression, health monitoring,
automatic promotion, and rollback capabilities.

Public API:
    - CanaryManager: Unified entry point
    - CanaryDeployment: Deployment instance
    - CanaryStage: Stage configuration
    - CanaryPolicy: Deployment policy
    - CanaryValidator: Configuration validation
    - CanaryMetrics: Prometheus metrics
    - CanaryAudit: Audit logging
    - CanaryMonitor: Real-time monitoring
    - HealthMonitor: Health check engine
    - HealthStatus: Status constants
    - RollbackManager: Rollback operations
    - PromotionEngine: Promotion evaluation
    - DEFAULT_CANARY_STAGES: Default stage progression
    - CONSERVATIVE_POLICY / BALANCED_POLICY / AGGRESSIVE_POLICY
"""

from __future__ import annotations

from .audit import CanaryAudit
from .deployment import CanaryDeploymentManager
from .health import HealthCheckResult, HealthMonitor, HealthStatus
from .manager import CanaryManager
from .metrics import CanaryMetrics
from .monitor import CanaryMonitor, MonitorSnapshot
from .policy import (
    AGGRESSIVE_POLICY,
    BALANCED_POLICY,
    CONSERVATIVE_POLICY,
    CanaryPolicy,
)
from .promotion import PromotionDecision, PromotionEngine
from .rollback import RollbackManager
from .stage import CanaryDeployment, CanaryStage, DEFAULT_CANARY_STAGES
from .validator import CanaryValidator

__all__ = [
    "CanaryManager",
    "CanaryDeployment",
    "CanaryStage",
    "CanaryPolicy",
    "CanaryDeploymentManager",
    "CanaryValidator",
    "CanaryMetrics",
    "CanaryAudit",
    "CanaryMonitor",
    "MonitorSnapshot",
    "HealthMonitor",
    "HealthCheckResult",
    "HealthStatus",
    "RollbackManager",
    "PromotionEngine",
    "PromotionDecision",
    "DEFAULT_CANARY_STAGES",
    "CONSERVATIVE_POLICY",
    "BALANCED_POLICY",
    "AGGRESSIVE_POLICY",
]
