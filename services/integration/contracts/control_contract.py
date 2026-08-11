"""Control Contract — the unified envelope for every cross-domain interaction.

This is the core abstraction of Part 1.2: every call between domains
(Risk, Governance, Authority, Approval) uses a ControlContract.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .control_version import ContractVersion
from .control_context import ContractControlContext
from .control_request import ControlRequest
from .control_response import ControlResponse
from .control_constraint import ControlConstraint
from .control_evidence import ControlEvidence
from .control_decision import ControlDecision
from .control_reference import ControlReference


@dataclass
class ControlContract:
    """The universal contract envelope for cross-domain institutional control.

    Every interaction between Strategy, Risk, Governance, Authority, Approval,
    and Order Admission is wrapped in this contract structure.

    Attributes:
        contract_id: Unique contract identifier.
        contract_version: Semantic version of the contract schema.
        domain: Target domain ("risk", "governance", "authority", "approval", "admission").
        request: The domain-specific request payload.
        context: Immutable control context carrying flow identity.
        decision: The final decision produced (populated after execution).
        constraints: Constraints produced by this domain.
        evidence: Audit evidence attached to the decision.
        references: Parent/child reference chain.
        created_at: When this contract was instantiated.
        expires_at: When this contract becomes invalid.
    """

    # ── Core identity ──

    contract_id: str = field(default_factory=lambda: f"CTR-{uuid.uuid4().hex[:12].upper()}")
    contract_version: str = "v1"
    domain: str = ""

    # ── Content ──

    request: ControlRequest = field(default_factory=ControlRequest)
    context: ContractControlContext = field(default_factory=ContractControlContext)

    # ── Results (populated after execution) ──

    response: Optional[ControlResponse] = None
    decision: Optional[ControlDecision] = None

    # ── Derived data ──

    constraints: List[ControlConstraint] = field(default_factory=list)
    evidence: List[ControlEvidence] = field(default_factory=list)
    references: List[ControlReference] = field(default_factory=list)

    # ── Timing ──

    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None

    # ── Metadata ──

    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)

    # ── Mutators (chainable) ──

    def with_request(self, request: ControlRequest) -> "ControlContract":
        self.request = request
        return self

    def with_context(self, context: ContractControlContext) -> "ControlContract":
        """Set context, verifying integrity against existing."""
        if self.context.flow_id and self.context.flow_id != context.flow_id:
            self.context.verify_integrity(context)
        self.context = context
        return self

    def with_response(self, response: ControlResponse) -> "ControlContract":
        self.response = response
        return self

    def with_constraints(self, constraints: List[ControlConstraint]) -> "ControlContract":
        self.constraints = constraints
        return self

    def with_evidence(self, evidence: List[ControlEvidence]) -> "ControlContract":
        self.evidence = evidence
        return self

    def add_constraint(self, constraint: ControlConstraint) -> "ControlContract":
        self.constraints.append(constraint)
        return self

    def add_evidence(self, evidence: ControlEvidence) -> "ControlContract":
        self.evidence.append(evidence)
        return self

    def add_reference(self, reference: ControlReference) -> "ControlContract":
        self.references.append(reference)
        return self

    def with_expiry(self, expires_at: float) -> "ControlContract":
        self.expires_at = expires_at
        return self

    def with_decision(self, decision: ControlDecision) -> "ControlContract":
        self.decision = decision
        return self

    def with_tag(self, key: str, value: str) -> "ControlContract":
        self.tags[key] = value
        return self

    # ── Properties ──

    @property
    def parsed_version(self) -> ContractVersion:
        return ContractVersion.parse(self.contract_version)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def is_executed(self) -> bool:
        return self.response is not None

    @property
    def is_decided(self) -> bool:
        return self.decision is not None

    @property
    def passed(self) -> bool:
        if self.response is None:
            return False
        return self.response.passed

    @property
    def summary(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "version": self.contract_version,
            "domain": self.domain,
            "flow_id": self.context.flow_id,
            "is_expired": self.is_expired,
            "is_executed": self.is_executed,
            "passed": self.passed,
            "constraint_count": len(self.constraints),
            "evidence_count": len(self.evidence),
            "reference_count": len(self.references),
        }

    # ── Factory ──

    @classmethod
    def create(
        cls,
        domain: str,
        request: ControlRequest,
        context: Optional[ContractControlContext] = None,
        version: str = "v1",
        **kwargs: Any,
    ) -> "ControlContract":
        """Create a new contract for a specific domain."""
        return cls(
            domain=domain,
            request=request,
            context=context or request.context,
            contract_version=version,
            **kwargs,
        )

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "domain": self.domain,
            "request": self.request.to_dict(),
            "context": self.context.to_dict(),
            "response": self.response.to_dict() if self.response else None,
            "decision": self.decision.to_dict() if self.decision else None,
            "constraints": [c.to_dict() for c in self.constraints],
            "evidence": [e.to_dict() for e in self.evidence],
            "references": [r.to_dict() for r in self.references],
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "metadata": self.metadata,
            "tags": self.tags,
        }

    def __repr__(self) -> str:
        executed = " EXECUTED" if self.is_executed else ""
        passed = " PASS" if self.passed else ""
        return (
            f"ControlContract(id={self.contract_id!r}, domain={self.domain!r}, "
            f"{self.contract_version}{executed}{passed})"
        )
