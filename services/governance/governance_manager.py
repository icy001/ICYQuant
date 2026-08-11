"""
Governance Manager — coordinates governance components and provides a high-level API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .governance_engine import GovernanceEngine, GovernanceEvaluation, GovernanceVerdict
from .governance_runtime import GovernanceRuntime, GovernanceRuntimeConfig
from .decision_context import DecisionContext
from .decision_request import DecisionRequest
from .decision_result import DecisionResult
from .policy_engine import PolicyEngine
from .authority_engine import AuthorityEngine
from .approval_engine import ApprovalEngine
from .decision_guard import DecisionGuard
from .decision_audit import DecisionAudit
from .governance_event_store import GovernanceEventStore
from .policy import Policy
from .governance_constraint import GovernanceConstraint


@dataclass
class GovernanceManagerConfig:
    """Manager-level configuration."""

    enabled: bool = True
    strict_mode: bool = False
    default_verdict_on_error: str = "REJECT"
    auto_register_defaults: bool = True

    # Component overrides
    policy_engine: Optional[PolicyEngine] = None
    authority_engine: Optional[AuthorityEngine] = None
    approval_engine: Optional[ApprovalEngine] = None
    decision_guard: Optional[DecisionGuard] = None
    auditor: Optional[DecisionAudit] = None
    event_store: Optional[GovernanceEventStore] = None

    # Runtime config
    runtime_config: Optional[GovernanceRuntimeConfig] = None


class GovernanceManager:
    """
    Top-level manager for the governance subsystem.
    Owns component lifecycle, policy registration, and constraint management.
    """

    def __init__(self, config: Optional[GovernanceManagerConfig] = None):
        self._config = config or GovernanceManagerConfig()

        # Components
        self._policy_engine = self._config.policy_engine or PolicyEngine()
        self._authority_engine = self._config.authority_engine or AuthorityEngine()
        self._approval_engine = self._config.approval_engine or ApprovalEngine()
        self._decision_guard = self._config.decision_guard or DecisionGuard()
        self._auditor = self._config.auditor or DecisionAudit()
        self._event_store = self._config.event_store or GovernanceEventStore()

        # Engine
        self._engine = GovernanceEngine(
            policy_engine=self._policy_engine,
            authority_engine=self._authority_engine,
            approval_engine=self._approval_engine,
            decision_guard=self._decision_guard,
            auditor=self._auditor,
            event_store=self._event_store,
        )

        # Runtime
        self._runtime = GovernanceRuntime(
            engine=self._engine,
            config=self._config.runtime_config,
        )

        # Extra constraints
        self._extra_constraints: List[GovernanceConstraint] = []

        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._started and self._config.enabled

    @property
    def engine(self) -> GovernanceEngine:
        return self._engine

    @property
    def runtime(self) -> GovernanceRuntime:
        return self._runtime

    @property
    def policy_engine(self) -> PolicyEngine:
        return self._policy_engine

    @property
    def authority_engine(self) -> AuthorityEngine:
        return self._authority_engine

    @property
    def auditor(self) -> DecisionAudit:
        return self._auditor

    def start(self) -> None:
        if self._config.auto_register_defaults:
            self._register_defaults()
        self._runtime.start()
        self._started = True

    def stop(self) -> None:
        self._runtime.stop()
        self._started = False

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def register_policy(self, policy: Policy) -> None:
        self._policy_engine.register(policy)

    def remove_policy(self, policy_id: str) -> None:
        self._policy_engine.remove(policy_id)

    def get_policies(self) -> List[Policy]:
        return self._policy_engine.list_policies()

    # ------------------------------------------------------------------
    # Constraint management
    # ------------------------------------------------------------------

    def register_constraint(self, constraint: GovernanceConstraint) -> None:
        self._extra_constraints.append(constraint)

    def clear_extra_constraints(self) -> None:
        self._extra_constraints.clear()

    # ------------------------------------------------------------------
    # Authority management
    # ------------------------------------------------------------------

    def set_authority(self, actor: str, decision_type: str, authorized: bool,
                      max_amount: float = float("inf"), scope: str = "GLOBAL") -> None:
        self._authority_engine.grant(actor, decision_type, authorized,
                                     max_amount=max_amount, scope=scope)

    def revoke_authority(self, actor: str, decision_type: str) -> None:
        self._authority_engine.revoke(actor, decision_type)

    # ------------------------------------------------------------------
    # Decision API
    # ------------------------------------------------------------------

    def evaluate(self, request: DecisionRequest, context: DecisionContext) -> DecisionResult:
        if not self._config.enabled:
            return DecisionResult.allowed(request.request_id, "governance disabled")

        # Inject extra constraints
        for constraint in self._extra_constraints:
            result = constraint.evaluate(request, context)
            if result.blocking:
                return DecisionResult.rejected(
                    request.request_id,
                    f"Extra constraint [{constraint.name}] blocked: {result.reason}",
                )

        return self._runtime.evaluate(request, context)

    def is_allowed(self, request: DecisionRequest, context: DecisionContext) -> bool:
        result = self.evaluate(request, context)
        return result.is_allowed

    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._auditor.query(limit=limit)

    def get_snapshot(self) -> Dict[str, Any]:
        return {
            "enabled": self._config.enabled,
            "started": self._started,
            "runtime": self._runtime.get_snapshot(),
            "policies_count": len(self._policy_engine.list_policies()),
            "audit_records": self._auditor.count(),
            "events": self._event_store.count(),
            "extra_constraints": len(self._extra_constraints),
        }

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------

    def _register_defaults(self) -> None:
        """Register sensible default policies."""
        # These defaults can be overridden by explicit registration
        pass
