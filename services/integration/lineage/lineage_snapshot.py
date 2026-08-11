"""Decision Snapshot — frozen point-in-time evidence of control decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DecisionSnapshot:
    """An immutable snapshot of control state at a decision point.

    Captures risk exposure, governance state, authority limits, and
    approval scope *as they were at the time of the decision* — not
    as they currently are.  This is critical for audit fidelity.
    """

    snapshot_id: str = field(
        default_factory=lambda: (
            f"SNAP-{__import__('uuid').uuid4().hex[:12].upper()}"
        ),
    )
    lineage_id: str = ""
    node_id: str = ""
    """The lineage node this snapshot is associated with."""

    timestamp: float = field(
        default_factory=lambda: __import__("time").time(),
    )

    # ── Risk evidence ─────────────────────────────────────────────
    risk_exposure: float = 0.0
    risk_limit: float = 0.0
    available_margin: float = 0.0
    risk_policy_version: str = ""

    # ── Governance evidence ───────────────────────────────────────
    governance_state: str = "NORMAL"
    governance_policy_version: str = ""

    # ── Authority evidence ────────────────────────────────────────
    authority_limit: float = 0.0
    authority_requested: float = 0.0
    authority_policy_version: str = ""

    # ── Approval evidence ─────────────────────────────────────────
    approval_id: str = ""
    approval_scope: str = ""
    approval_policy_version: str = ""

    # ── Decision context ──────────────────────────────────────────
    decision_type: str = ""
    decision_reason: str = ""
    max_notional: float = 0.0

    # ── Extensible ────────────────────────────────────────────────
    extra: dict[str, Any] = field(default_factory=dict)

    # ── Properties ────────────────────────────────────────────────

    @property
    def is_governance_normal(self) -> bool:
        return self.governance_state.upper() == "NORMAL"

    @property
    def is_within_risk_limit(self) -> bool:
        if self.risk_limit <= 0:
            return True  # no limit configured
        return self.risk_exposure <= self.risk_limit

    @property
    def is_within_authority_limit(self) -> bool:
        if self.authority_limit <= 0:
            return True
        return self.authority_requested <= self.authority_limit

    # ── Factory methods ───────────────────────────────────────────

    @classmethod
    def for_decision(cls, lineage_id: str, node_id: str,
                     decision_type: str = "",
                     decision_reason: str = "",
                     ) -> "DecisionSnapshot":
        """Create a minimal snapshot for a decision node."""
        import time as _t
        return cls(
            lineage_id=lineage_id,
            node_id=node_id,
            timestamp=_t.time(),
            decision_type=decision_type,
            decision_reason=decision_reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "lineage_id": self.lineage_id,
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "risk_exposure": self.risk_exposure,
            "risk_limit": self.risk_limit,
            "available_margin": self.available_margin,
            "risk_policy_version": self.risk_policy_version,
            "governance_state": self.governance_state,
            "governance_policy_version": self.governance_policy_version,
            "authority_limit": self.authority_limit,
            "authority_requested": self.authority_requested,
            "authority_policy_version": self.authority_policy_version,
            "approval_id": self.approval_id,
            "approval_scope": self.approval_scope,
            "approval_policy_version": self.approval_policy_version,
            "decision_type": self.decision_type,
            "decision_reason": self.decision_reason,
            "max_notional": self.max_notional,
            "extra": dict(self.extra),
        }
