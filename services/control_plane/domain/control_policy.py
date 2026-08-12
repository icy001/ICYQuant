"""
Control Policy layer — the rules are NOT hard-coded inside if/else spread over
the codebase, they live in dedicated policies:

    ControlPolicy (base)
        ├── TradingPolicy      (implemented in this part)
        ├── RecoveryPolicy     (future)
        ├── MaintenancePolicy  (future)
        └── EmergencyPolicy    (future)

A policy never executes an action; it returns a PolicyResult:

    decision = DENY
    severity = CRITICAL
    reason   = RISK_ENGINE_UNHEALTHY

The Control Plane translates PolicyResult → Trading State → Trading Gate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from .component_registry import ComponentType
from .component_state import ComponentState
from .system_state import StateReasonCode
from .trading_gate import RiskIntegrity, Severity


class PolicyDecision(str, Enum):
    """Outcome level produced by a policy."""

    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    DENY = "DENY"


@dataclass
class PolicyContext:
    """Inputs consumed by a policy evaluation."""

    component_states: Dict[str, ComponentState] = field(default_factory=dict)
    risk_integrity: RiskIntegrity = RiskIntegrity.TRUSTED
    consistency_status: Optional[str] = None
    recovery_active: bool = False


@dataclass
class PolicyResult:
    """Result of a policy evaluation — an *advice*, never an action."""

    policy_name: str
    decision: PolicyDecision
    severity: Severity
    reason: StateReasonCode
    source: str = "policy"
    detail: str = ""

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_name": self.policy_name,
            "decision": self.decision.value,
            "severity": self.severity.value,
            "reason": self.reason.value,
            "source": self.source,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyResult":
        return cls(
            policy_name=data["policy_name"],
            decision=PolicyDecision(data["decision"]),
            severity=Severity(data["severity"]),
            reason=StateReasonCode(data["reason"]),
            source=data.get("source", "policy"),
            detail=data.get("detail", ""),
        )


class ControlPolicy(ABC):
    """Base class for all control policies."""

    name: str = "CONTROL_POLICY"

    @abstractmethod
    def evaluate(self, context: PolicyContext) -> PolicyResult:  # pragma: no cover - abstract
        ...


# Critical components → DENY outright when not HEALTHY.
_CRITICAL_POLICY_REASON: Dict[str, StateReasonCode] = {
    "event_bus": StateReasonCode.EVENT_BUS_UNAVAILABLE,
    "risk_engine": StateReasonCode.RISK_ENGINE_UNHEALTHY,
    "execution_engine": StateReasonCode.EXECUTION_ENGINE_UNHEALTHY,
}


class TradingPolicy(ControlPolicy):
    """
    Determines whether trading should be ALLOW / REVIEW / DENY based on the
    component state map and Risk Integrity.

        Event Bus / Risk / Execution  != HEALTHY        → DENY (CRITICAL)
        Risk Integrity UNTRUSTED                        → DENY (CRITICAL)
        Position / Ledger degraded                      → REVIEW (WARNING)
        Any other component degraded / non-critical     → ALLOW
    """

    name = "TRADING_POLICY"

    #: Components whose degradation triggers a REVIEW instead of ALLOW.
    REVIEW_COMPONENT_IDS: tuple = (
        ComponentType.POSITION_SERVICE.value,
        ComponentType.LEDGER_SERVICE.value,
    )

    def evaluate(self, context: PolicyContext) -> PolicyResult:
        states = context.component_states

        # 1. Trading-critical components must be HEALTHY.
        for component_id, reason in _CRITICAL_POLICY_REASON.items():
            state = states.get(component_id)
            if state is None or state is not ComponentState.HEALTHY:
                return PolicyResult(
                    policy_name=self.name,
                    decision=PolicyDecision.DENY,
                    severity=Severity.CRITICAL,
                    reason=reason,
                    source=component_id,
                )

        # 2. Risk integrity cannot be guaranteed.
        if context.risk_integrity is RiskIntegrity.UNTRUSTED:
            return PolicyResult(
                policy_name=self.name,
                decision=PolicyDecision.DENY,
                severity=Severity.CRITICAL,
                reason=StateReasonCode.RISK_INTEGRITY_DEGRADED,
                source="risk-engine",
            )

        # 3. Position / Ledger — the consistency-sensitive core inputs.
        for component_id, reason in (
            (ComponentType.POSITION_SERVICE.value, StateReasonCode.POSITION_MISMATCH),
            (ComponentType.LEDGER_SERVICE.value, StateReasonCode.LEDGER_MISMATCH),
        ):
            state = states.get(component_id)
            if state is not None and state is not ComponentState.HEALTHY:
                return PolicyResult(
                    policy_name=self.name,
                    decision=PolicyDecision.REVIEW,
                    severity=Severity.WARNING,
                    reason=reason,
                    source=component_id,
                )

        # 4. Remaining components only affect quality, not permission.
        return PolicyResult(
            policy_name=self.name,
            decision=PolicyDecision.ALLOW,
            severity=Severity.INFO,
            reason=StateReasonCode.SYSTEM_HEALTHY,
            source="trading-policy",
        )
