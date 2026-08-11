"""
Control Context — unified context carried through the entire trading control flow.

Commit 21 Part 1.1: every trade/decision carries a TradingControlContext
that links Strategy → Signal → Decision → Risk → Governance → Authority
→ Approval → Order → Execution, enabling full audit correlation.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TradingControlContext:
    """Unified context carried through the entire institutional control flow.

    This context answers:
      - Who produced this trade?
      - Why was it produced?
      - What risk checks were applied?
      - Which policy was used?
      - Who authorized it?
      - Who approved it?
      - What order did it become?
    """

    # ── Flow Identity ──────────────────────────────────────────
    flow_id: str = field(default_factory=lambda: f"FLOW-{uuid.uuid4().hex[:12].upper()}")

    # ── Origin ─────────────────────────────────────────────────
    strategy_id: Optional[str] = None
    signal_id: Optional[str] = None
    decision_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    account_id: Optional[str] = None

    # ── Domain Contexts ────────────────────────────────────────
    risk_context: Optional[Dict[str, Any]] = None
    governance_context: Optional[Dict[str, Any]] = None
    authority_context: Optional[Dict[str, Any]] = None
    approval_context: Optional[Dict[str, Any]] = None

    # ── Version Pinning ────────────────────────────────────────
    policy_version: Optional[str] = None
    risk_version: Optional[str] = None
    governance_version: Optional[str] = None

    # ── Idempotency ────────────────────────────────────────────
    idempotency_key: Optional[str] = None

    # ── Metadata ───────────────────────────────────────────────
    actor: str = "SYSTEM"
    decision_type: str = ""
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Timestamps ─────────────────────────────────────────────
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = time.time()

    def with_risk_context(self, ctx: Dict[str, Any]) -> "TradingControlContext":
        """Attach risk context and return self for chaining."""
        self.risk_context = ctx
        self.touch()
        return self

    def with_governance_context(self, ctx: Dict[str, Any]) -> "TradingControlContext":
        """Attach governance context and return self for chaining."""
        self.governance_context = ctx
        self.touch()
        return self

    def with_authority_context(self, ctx: Dict[str, Any]) -> "TradingControlContext":
        """Attach authority context and return self for chaining."""
        self.authority_context = ctx
        self.touch()
        return self

    def with_approval_context(self, ctx: Dict[str, Any]) -> "TradingControlContext":
        """Attach approval context and return self for chaining."""
        self.approval_context = ctx
        self.touch()
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "strategy_id": self.strategy_id,
            "signal_id": self.signal_id,
            "decision_id": self.decision_id,
            "portfolio_id": self.portfolio_id,
            "account_id": self.account_id,
            "risk_context": self.risk_context,
            "governance_context": self.governance_context,
            "authority_context": self.authority_context,
            "approval_context": self.approval_context,
            "policy_version": self.policy_version,
            "risk_version": self.risk_version,
            "governance_version": self.governance_version,
            "idempotency_key": self.idempotency_key,
            "actor": self.actor,
            "decision_type": self.decision_type,
            "reason": self.reason,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_decision(
        cls,
        decision_id: str,
        strategy_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        actor: str = "SYSTEM",
        decision_type: str = "",
        reason: str = "",
    ) -> "TradingControlContext":
        """Create a context seeded from a decision."""
        return cls(
            decision_id=decision_id,
            strategy_id=strategy_id,
            portfolio_id=portfolio_id,
            actor=actor,
            decision_type=decision_type,
            reason=reason,
        )
