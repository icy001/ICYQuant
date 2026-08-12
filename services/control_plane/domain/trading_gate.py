"""
TradingGate — the single "CanTrade?" decision point.

The gate answers one question: ALLOW or DENY.

    Risk Engine = HEALTHY
    Event Bus   = HEALTHY      --->  ALLOW
    Execution   = HEALTHY

    Event Bus   != HEALTHY     --->  DENY
    Risk Engine != HEALTHY     --->  DENY
    Execution   != HEALTHY     --->  DENY

    Analytics   != HEALTHY     --->  ALLOW   (non-critical, no impact)

Position / Ledger degradation does NOT immediately halt trading: the gate only
DENYs when Risk Integrity cannot be guaranteed (risk_integrity == UNTRUSTED).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .component_registry import TRADING_CRITICAL_IDS
from .component_state import ComponentState
from .system_state import StateReasonCode


class Severity(str, Enum):
    """Severity of a decision or policy result."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class GateDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class RiskIntegrity(str, Enum):
    """Whether the Risk Engine can trust its Position / Balance / Exposure inputs."""

    TRUSTED = "TRUSTED"
    DEGRADED = "DEGRADED"
    UNTRUSTED = "UNTRUSTED"


# Canonical reason code per trading-critical component type.
_CRITICAL_REASON: Dict[str, StateReasonCode] = {
    "event_bus": StateReasonCode.EVENT_BUS_UNAVAILABLE,
    "risk_engine": StateReasonCode.RISK_ENGINE_UNHEALTHY,
    "execution_engine": StateReasonCode.EXECUTION_ENGINE_UNHEALTHY,
}


@dataclass
class TradingGateResult:
    """Outcome of a TradingGate evaluation."""

    decision: GateDecision
    reason: StateReasonCode = StateReasonCode.SYSTEM_HEALTHY
    severity: Severity = Severity.INFO
    source: str = "trading-gate"
    blocked_components: List[str] = field(default_factory=list)
    risk_integrity: RiskIntegrity = RiskIntegrity.TRUSTED
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason": self.reason.value,
            "severity": self.severity.value,
            "source": self.source,
            "blocked_components": list(self.blocked_components),
            "risk_integrity": self.risk_integrity.value,
            "checked_at": self.checked_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradingGateResult":
        return cls(
            decision=GateDecision(data["decision"]),
            reason=StateReasonCode(data["reason"]),
            severity=Severity(data["severity"]),
            source=data.get("source", "trading-gate"),
            blocked_components=list(data.get("blocked_components", [])),
            risk_integrity=RiskIntegrity(data["risk_integrity"]),
            checked_at=datetime.fromisoformat(data["checked_at"]),
        )


class TradingGate:
    """
    Deterministic gate over component states + risk integrity.

    ``states`` is keyed by canonical component id (see ComponentRegistry).
    """

    TRADING_CRITICAL_IDS: tuple = TRADING_CRITICAL_IDS

    def evaluate(
        self,
        states: Dict[str, ComponentState],
        risk_integrity: RiskIntegrity = RiskIntegrity.TRUSTED,
        at: Optional[datetime] = None,
    ) -> TradingGateResult:
        checked_at = at or datetime.now(timezone.utc)

        # 1. Trading-critical components must be HEALTHY.
        blocked: List[str] = []
        for component_id in self.TRADING_CRITICAL_IDS:
            state = states.get(component_id)
            if state is None or state is not ComponentState.HEALTHY:
                blocked.append(component_id)

        if blocked:
            return TradingGateResult(
                decision=GateDecision.DENY,
                reason=_CRITICAL_REASON[blocked[0]],
                severity=Severity.CRITICAL,
                source=blocked[0],
                blocked_components=blocked,
                risk_integrity=risk_integrity,
                checked_at=checked_at,
            )

        # 2. If the Risk Engine cannot trust its inputs, trading cannot be safe.
        if risk_integrity is RiskIntegrity.UNTRUSTED:
            return TradingGateResult(
                decision=GateDecision.DENY,
                reason=StateReasonCode.RISK_INTEGRITY_DEGRADED,
                severity=Severity.CRITICAL,
                source="risk-engine",
                blocked_components=["position_service"],
                risk_integrity=risk_integrity,
                checked_at=checked_at,
            )

        # 3. Everything else (incl. non-critical components) → ALLOW.
        return TradingGateResult(
            decision=GateDecision.ALLOW,
            reason=StateReasonCode.SYSTEM_HEALTHY,
            severity=Severity.INFO,
            source="trading-gate",
            risk_integrity=risk_integrity,
            checked_at=checked_at,
        )
