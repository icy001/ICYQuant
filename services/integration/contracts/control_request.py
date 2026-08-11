"""Unified control requests for cross-domain communication.

Each domain (Risk, Governance, Authority, Approval) has a specific request
type that can be serialized into the generic ControlRequest envelope.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .control_context import ContractControlContext


@dataclass
class ControlRequest:
    """Generic cross-domain control request envelope.

    All domain-specific requests (RiskRequest, GovernanceRequest, etc.)
    are convertible to this unified format.
    """

    # ── Identity ──
    request_id: str = field(default_factory=lambda: f"REQ-{uuid.uuid4().hex[:12].upper()}")
    domain: str = ""  # "risk", "governance", "authority", "approval"

    # ── Context ──
    context: ContractControlContext = field(default_factory=ContractControlContext)

    # ── Payload ──
    payload: Dict[str, Any] = field(default_factory=dict)

    # ── Metadata ──
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = 60.0  # default 1-minute TTL
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Domain-specific factory methods ──

    @classmethod
    def from_risk_request(cls, req: "RiskRequest") -> "ControlRequest":
        return cls(
            domain="risk",
            context=req.context,
            payload={
                "symbol": req.symbol,
                "side": req.side,
                "quantity": req.quantity,
                "notional": req.notional,
                "order_type": req.order_type,
                "risk_data": req.risk_data,
            },
            metadata={"source_request_id": req.request_id},
        )

    @classmethod
    def from_governance_request(cls, req: "GovernanceRequest") -> "ControlRequest":
        return cls(
            domain="governance",
            context=req.context,
            payload={
                "policy_name": req.policy_name,
                "policy_version": req.policy_version,
                "governance_data": req.governance_data,
            },
            metadata={"source_request_id": req.request_id},
        )

    @classmethod
    def from_authority_request(cls, req: "AuthorityRequest") -> "ControlRequest":
        return cls(
            domain="authority",
            context=req.context,
            payload={
                "trader_id": req.trader_id,
                "requested_notional": req.requested_notional,
                "authority_data": req.authority_data,
            },
            metadata={"source_request_id": req.request_id},
        )

    @classmethod
    def from_approval_request(cls, req: "ApprovalRequest") -> "ControlRequest":
        return cls(
            domain="approval",
            context=req.context,
            payload={
                "approval_id": req.approval_id,
                "requested_notional": req.requested_notional,
                "scope": req.scope,
                "approval_data": req.approval_data,
            },
            metadata={"source_request_id": req.request_id},
        )

    @property
    def is_expired(self) -> bool:
        return time.time() > self.created_at + self.ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "domain": self.domain,
            "context": self.context.to_dict(),
            "payload": self.payload,
            "created_at": self.created_at,
            "ttl_seconds": self.ttl_seconds,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return f"ControlRequest(domain={self.domain!r}, request_id={self.request_id!r})"


# ── Domain-specific request types ──


@dataclass
class RiskRequest:
    """Risk-domain control request."""

    # ── Identity ──
    request_id: str = field(default_factory=lambda: f"RISK-{uuid.uuid4().hex[:12].upper()}")

    # ── Context ──
    context: ContractControlContext = field(default_factory=ContractControlContext)

    # ── Trade parameters ──
    symbol: str = ""
    side: str = ""
    quantity: float = 0.0
    notional: float = 0.0
    order_type: str = ""

    # ── Risk data ──
    risk_data: Dict[str, Any] = field(default_factory=dict)

    def to_control_request(self) -> ControlRequest:
        return ControlRequest.from_risk_request(self)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "context": self.context.to_dict(),
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "notional": self.notional,
            "order_type": self.order_type,
            "risk_data": self.risk_data,
        }


@dataclass
class GovernanceRequest:
    """Governance-domain control request."""

    # ── Identity ──
    request_id: str = field(default_factory=lambda: f"GOV-{uuid.uuid4().hex[:12].upper()}")

    # ── Context ──
    context: ContractControlContext = field(default_factory=ContractControlContext)

    # ── Policy ──
    policy_name: str = ""
    policy_version: str = ""

    # ── Governance data ──
    governance_data: Dict[str, Any] = field(default_factory=dict)

    def to_control_request(self) -> ControlRequest:
        return ControlRequest.from_governance_request(self)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "context": self.context.to_dict(),
            "policy_name": self.policy_name,
            "policy_version": self.policy_version,
            "governance_data": self.governance_data,
        }


@dataclass
class AuthorityRequest:
    """Authority-domain control request."""

    # ── Identity ──
    request_id: str = field(default_factory=lambda: f"AUTH-{uuid.uuid4().hex[:12].upper()}")

    # ── Context ──
    context: ContractControlContext = field(default_factory=ContractControlContext)

    # ── Authority parameters ──
    trader_id: str = ""
    requested_notional: float = 0.0

    # ── Authority data ──
    authority_data: Dict[str, Any] = field(default_factory=dict)

    def to_control_request(self) -> ControlRequest:
        return ControlRequest.from_authority_request(self)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "context": self.context.to_dict(),
            "trader_id": self.trader_id,
            "requested_notional": self.requested_notional,
            "authority_data": self.authority_data,
        }


@dataclass
class ApprovalRequest:
    """Approval-domain control request."""

    # ── Identity ──
    request_id: str = field(default_factory=lambda: f"APR-{uuid.uuid4().hex[:12].upper()}")

    # ── Context ──
    context: ContractControlContext = field(default_factory=ContractControlContext)

    # ── Approval parameters ──
    approval_id: str = ""
    requested_notional: float = 0.0
    scope: str = ""

    # ── Approval data ──
    approval_data: Dict[str, Any] = field(default_factory=dict)

    def to_control_request(self) -> ControlRequest:
        return ControlRequest.from_approval_request(self)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "context": self.context.to_dict(),
            "approval_id": self.approval_id,
            "requested_notional": self.requested_notional,
            "scope": self.scope,
            "approval_data": self.approval_data,
        }
