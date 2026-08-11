"""Unified control response — every domain returns this envelope."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional

from .control_reason import ReasonCode
from .control_evidence import ControlEvidence


class ControlResponseStatus(Enum):
    """Unified status for all domain control responses."""

    PASS = auto()
    REJECT = auto()
    BLOCK = auto()
    FREEZE = auto()
    EXPIRED = auto()
    ERROR = auto()

    @property
    def label(self) -> str:
        _labels = {
            ControlResponseStatus.PASS: "PASS",
            ControlResponseStatus.REJECT: "REJECT",
            ControlResponseStatus.BLOCK: "BLOCK",
            ControlResponseStatus.FREEZE: "FREEZE",
            ControlResponseStatus.EXPIRED: "EXPIRED",
            ControlResponseStatus.ERROR: "ERROR",
        }
        return _labels.get(self, "UNKNOWN")

    @property
    def is_pass(self) -> bool:
        return self == ControlResponseStatus.PASS

    @property
    def is_terminal(self) -> bool:
        return self in (
            ControlResponseStatus.REJECT,
            ControlResponseStatus.BLOCK,
            ControlResponseStatus.FREEZE,
            ControlResponseStatus.EXPIRED,
            ControlResponseStatus.ERROR,
        )


@dataclass
class ControlResponse:
    """Unified response envelope from any control domain gate.

    Every domain (Risk, Governance, Authority, Approval) returns this
    exact structure, enabling uniform orchestration.
    """

    # ── Core ──

    response_id: str = field(default_factory=lambda: f"RSP-{uuid.uuid4().hex[:12].upper()}")
    domain: str = ""  # "risk", "governance", "authority", "approval"
    status: ControlResponseStatus = ControlResponseStatus.PASS
    reason_code: ReasonCode = ReasonCode.RISK_CHECK_PASSED
    reason: str = ""

    # ── Correlation ──

    flow_id: str = ""
    request_id: str = ""
    contract_id: str = ""

    # ── Evidence ──

    evidence: Optional[ControlEvidence] = None

    # ── Constraints ──

    constraints: Dict[str, Any] = field(default_factory=dict)

    # ── Timing ──

    timestamp: float = field(default_factory=time.time)
    latency_ms: float = 0.0

    # ── Metadata ──

    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Factory methods ──

    @classmethod
    def make_pass(
        cls,
        domain: str,
        reason_code: ReasonCode,
        reason: str = "",
        flow_id: str = "",
        request_id: str = "",
        contract_id: str = "",
        evidence: Optional[ControlEvidence] = None,
        constraints: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "ControlResponse":
        return cls(
            domain=domain,
            status=ControlResponseStatus.PASS,
            reason_code=reason_code,
            reason=reason,
            flow_id=flow_id,
            request_id=request_id,
            contract_id=contract_id,
            evidence=evidence,
            constraints=constraints or {},
            **kwargs,
        )

    @classmethod
    def make_reject(
        cls,
        domain: str,
        reason_code: ReasonCode,
        reason: str = "",
        flow_id: str = "",
        request_id: str = "",
        contract_id: str = "",
        evidence: Optional[ControlEvidence] = None,
        **kwargs: Any,
    ) -> "ControlResponse":
        return cls(
            domain=domain,
            status=ControlResponseStatus.REJECT,
            reason_code=reason_code,
            reason=reason,
            flow_id=flow_id,
            request_id=request_id,
            contract_id=contract_id,
            evidence=evidence,
            **kwargs,
        )

    @classmethod
    def make_block(
        cls,
        domain: str,
        reason_code: ReasonCode,
        reason: str = "",
        flow_id: str = "",
        request_id: str = "",
        contract_id: str = "",
        evidence: Optional[ControlEvidence] = None,
        **kwargs: Any,
    ) -> "ControlResponse":
        return cls(
            domain=domain,
            status=ControlResponseStatus.BLOCK,
            reason_code=reason_code,
            reason=reason,
            flow_id=flow_id,
            request_id=request_id,
            contract_id=contract_id,
            evidence=evidence,
            **kwargs,
        )

    @classmethod
    def make_freeze(
        cls,
        domain: str,
        reason_code: ReasonCode,
        reason: str = "",
        flow_id: str = "",
        request_id: str = "",
        contract_id: str = "",
        evidence: Optional[ControlEvidence] = None,
        **kwargs: Any,
    ) -> "ControlResponse":
        return cls(
            domain=domain,
            status=ControlResponseStatus.FREEZE,
            reason_code=reason_code,
            reason=reason,
            flow_id=flow_id,
            request_id=request_id,
            contract_id=contract_id,
            evidence=evidence,
            **kwargs,
        )

    @classmethod
    def make_expired(
        cls,
        domain: str,
        reason_code: ReasonCode = ReasonCode.CONTRACT_EXPIRED,
        reason: str = "",
        flow_id: str = "",
        request_id: str = "",
        contract_id: str = "",
        **kwargs: Any,
    ) -> "ControlResponse":
        return cls(
            domain=domain,
            status=ControlResponseStatus.EXPIRED,
            reason_code=reason_code,
            reason=reason,
            flow_id=flow_id,
            request_id=request_id,
            contract_id=contract_id,
            **kwargs,
        )

    @classmethod
    def make_error(
        cls,
        domain: str,
        reason: str = "",
        flow_id: str = "",
        request_id: str = "",
        contract_id: str = "",
        **kwargs: Any,
    ) -> "ControlResponse":
        return cls(
            domain=domain,
            status=ControlResponseStatus.ERROR,
            reason_code=ReasonCode.UNKNOWN_ERROR,
            reason=reason,
            flow_id=flow_id,
            request_id=request_id,
            contract_id=contract_id,
            **kwargs,
        )

    # ── Properties ──

    @property
    def passed(self) -> bool:
        return self.status.is_pass

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_id": self.response_id,
            "domain": self.domain,
            "status": self.status.name,
            "reason_code": self.reason_code.name,
            "reason": self.reason,
            "flow_id": self.flow_id,
            "request_id": self.request_id,
            "contract_id": self.contract_id,
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "constraints": self.constraints,
            "timestamp": self.timestamp,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"ControlResponse(domain={self.domain!r}, status={self.status.label}, "
            f"code={self.reason_code.name})"
        )
