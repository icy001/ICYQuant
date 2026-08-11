"""
Governance State — runtime governance state snapshot.

Part 1.5: captures the current governance system state including active
policy versions, authority grants, approval statuses, and health signals.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .control_state import GovernanceStateType


@dataclass
class GovernanceRuntimeState:
    """A snapshot of the governance runtime state.

    Used by the monitor and control plane to detect anomalies.
    """

    # State
    governance_state: GovernanceStateType = GovernanceStateType.NORMAL
    state_since: float = field(default_factory=time.time)

    # Risk metrics
    portfolio_drawdown: float = 0.0
    value_at_risk: float = 0.0
    portfolio_exposure: float = 0.0
    leverage_ratio: float = 1.0
    liquidity_score: float = 1.0
    stress_score: float = 0.0
    concentration_hhi: float = 0.0

    # Execution metrics
    execution_slippage_bps: float = 0.0
    order_rejection_rate: float = 0.0
    execution_latency_ms: float = 0.0

    # Policy metrics
    active_policy_count: int = 0
    policy_conflicts: int = 0
    policy_breaches_24h: int = 0

    # Authority metrics
    active_authority_grants: int = 0
    authority_expiries_pending: int = 0

    # Approval metrics
    pending_approvals: int = 0
    expired_approvals: int = 0

    # Audit metrics
    audit_integrity_valid: bool = True
    audit_chain_intact: bool = True
    audit_events_24h: int = 0

    # Health
    risk_engine_healthy: bool = True
    policy_engine_healthy: bool = True
    approval_engine_healthy: bool = True
    audit_engine_healthy: bool = True

    # Timestamp
    observed_at: float = field(default_factory=time.time)

    def get_breaches(self, thresholds: List[Any]) -> List[Dict[str, Any]]:
        """Check this state against a list of GovernanceThreshold objects."""
        metric_map = {
            "portfolio_drawdown": self.portfolio_drawdown,
            "value_at_risk": self.value_at_risk,
            "portfolio_exposure": self.portfolio_exposure,
            "leverage_ratio": self.leverage_ratio,
            "liquidity_score": self.liquidity_score,
            "stress_score": self.stress_score,
            "execution_slippage_bps": self.execution_slippage_bps,
        }

        breaches = []
        for thresh in thresholds:
            if not thresh.enabled:
                continue
            observed = metric_map.get(thresh.metric)
            if observed is not None and thresh.is_breached(observed):
                breaches.append({
                    "threshold_id": thresh.threshold_id,
                    "metric": thresh.metric,
                    "observed": observed,
                    "threshold": thresh.value,
                    "target_state": thresh.target_state.name,
                    "severity": thresh.severity.name,
                })
        return breaches

    def to_dict(self) -> Dict[str, Any]:
        return {
            "governance_state": self.governance_state.name,
            "state_since": self.state_since,
            "risk": {
                "drawdown": self.portfolio_drawdown,
                "var": self.value_at_risk,
                "exposure": self.portfolio_exposure,
                "leverage": self.leverage_ratio,
                "liquidity": self.liquidity_score,
                "stress": self.stress_score,
                "concentration": self.concentration_hhi,
            },
            "execution": {
                "slippage_bps": self.execution_slippage_bps,
                "rejection_rate": self.order_rejection_rate,
                "latency_ms": self.execution_latency_ms,
            },
            "policy": {
                "active_count": self.active_policy_count,
                "conflicts": self.policy_conflicts,
                "breaches_24h": self.policy_breaches_24h,
            },
            "authority": {
                "active_grants": self.active_authority_grants,
                "expiries_pending": self.authority_expiries_pending,
            },
            "approval": {
                "pending": self.pending_approvals,
                "expired": self.expired_approvals,
            },
            "audit": {
                "integrity_valid": self.audit_integrity_valid,
                "chain_intact": self.audit_chain_intact,
                "events_24h": self.audit_events_24h,
            },
            "health": {
                "risk_engine": self.risk_engine_healthy,
                "policy_engine": self.policy_engine_healthy,
                "approval_engine": self.approval_engine_healthy,
                "audit_engine": self.audit_engine_healthy,
            },
            "observed_at": self.observed_at,
        }

    @classmethod
    def create_default(cls) -> "GovernanceRuntimeState":
        return cls()
