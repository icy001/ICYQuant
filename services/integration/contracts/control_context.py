"""Contract-level control context — the identity envelope for every cross-domain call.

This is a lightweight, immutable-identity context that guarantees a request
never loses track of its originating flow.  It is distinct from
TradingControlContext (which carries mutable gate state).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .contract_errors import ContextIntegrityError


# ── Immutable core fields ──
IMMUTABLE_CONTEXT_FIELDS: tuple[str, ...] = (
    "flow_id",
    "decision_id",
    "strategy_id",
    "portfolio_id",
    "account_id",
)


@dataclass
class ContractControlContext:
    """Minimal identity context carried through every contract invocation.

    Core identity fields (flow_id, decision_id, strategy_id, portfolio_id,
    account_id) are immutable once set.  Policy versions may be updated
    as the flow progresses but MUST be validated against upstream values.
    """

    # ── Core Identity (immutable) ──

    flow_id: str = field(default_factory=lambda: f"FLOW-{uuid.uuid4().hex[:12].upper()}")
    decision_id: str = ""
    signal_id: str = ""
    strategy_id: str = ""
    portfolio_id: str = ""
    account_id: str = ""

    # ── Policy Versions (tracked per domain) ──

    policy_version: str = ""
    risk_version: str = ""
    governance_version: str = ""
    authority_version: str = ""
    approval_version: str = ""

    # ── Metadata ──

    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Immutability guard ──

    def verify_integrity(self, other: "ContractControlContext") -> None:
        """Verify that immutable core fields match another context.

        Raises ContextIntegrityError if any immutable field has been changed.
        """
        for field_name in IMMUTABLE_CONTEXT_FIELDS:
            self_val = getattr(self, field_name, "")
            other_val = getattr(other, field_name, "")
            if self_val and other_val and self_val != other_val:
                raise ContextIntegrityError(
                    message=f"Immutable field '{field_name}' was modified: "
                    f"expected '{self_val}', got '{other_val}'",
                    field=field_name,
                    expected=str(self_val),
                    actual=str(other_val),
                )

    def verify_self_consistent(self) -> None:
        """Verify that this context's own identity fields are self-consistent.

        Raises ContextIntegrityError if, for example, flow_id is empty.
        """
        if not self.flow_id:
            raise ContextIntegrityError(
                message="flow_id must not be empty",
                field="flow_id",
                expected="<non-empty>",
                actual="<empty>",
            )

    # ── Version tracking ──

    def with_risk_version(self, version: str) -> "ContractControlContext":
        self.risk_version = version
        return self

    def with_governance_version(self, version: str) -> "ContractControlContext":
        self.governance_version = version
        return self

    def with_authority_version(self, version: str) -> "ContractControlContext":
        self.authority_version = version
        return self

    def with_approval_version(self, version: str) -> "ContractControlContext":
        self.approval_version = version
        return self

    def with_policy_version(self, version: str) -> "ContractControlContext":
        self.policy_version = version
        return self

    # ── Getters ──

    def get(self, key: str, default: Any = None) -> Any:
        """Generic access to context fields by name."""
        if hasattr(self, key):
            return getattr(self, key, default)
        return self.metadata.get(key, default)

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "decision_id": self.decision_id,
            "signal_id": self.signal_id,
            "strategy_id": self.strategy_id,
            "portfolio_id": self.portfolio_id,
            "account_id": self.account_id,
            "policy_version": self.policy_version,
            "risk_version": self.risk_version,
            "governance_version": self.governance_version,
            "authority_version": self.authority_version,
            "approval_version": self.approval_version,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"ContractControlContext(flow_id={self.flow_id!r}, "
            f"decision_id={self.decision_id!r}, "
            f"strategy_id={self.strategy_id!r})"
        )
