"""Contract Serializer — serializes/deserializes cross-domain contracts to/from JSON.

Supports round-tripping contracts for:
  - Persistence (audit log)
  - Transport (message bus)
  - Cross-process communication
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .contracts.control_contract import ControlContract
from .contracts.control_request import (
    ControlRequest,
    RiskRequest,
    GovernanceRequest,
    AuthorityRequest,
    ApprovalRequest,
)
from .contracts.control_response import ControlResponse, ControlResponseStatus
from .contracts.control_context import ContractControlContext
from .contracts.control_constraint import ControlConstraint, ConstraintType, ConstraintRule, ConstraintSource
from .contracts.control_evidence import ControlEvidence
from .contracts.control_decision import ControlDecision, DecisionStatus
from .contracts.control_reference import ControlReference
from .contracts.control_reason import ReasonCode


@dataclass
class ContractSerializer:
    """Serializes and deserializes ControlContracts to/from dictionaries and JSON.

    Handles nested objects: request, response, context, constraints,
    evidence, references, and decision.
    """

    indent: int = 2
    ensure_ascii: bool = False

    # ── Serialize ──

    def serialize(self, contract: ControlContract) -> str:
        """Serialize a contract to a JSON string."""
        return json.dumps(contract.to_dict(), indent=self.indent, ensure_ascii=self.ensure_ascii)

    def serialize_dict(self, contract: ControlContract) -> Dict[str, Any]:
        """Serialize a contract to a plain dictionary."""
        return contract.to_dict()

    # ── Deserialize ──

    def deserialize(self, data: str) -> ControlContract:
        """Deserialize a JSON string back into a ControlContract."""
        d = json.loads(data)
        return self._from_dict(d)

    def _from_dict(self, d: Dict[str, Any]) -> ControlContract:
        """Reconstruct a ControlContract from a dictionary."""

        # Rebuild context
        ctx_data = d.get("context", {})
        context = ContractControlContext(
            flow_id=ctx_data.get("flow_id", ""),
            decision_id=ctx_data.get("decision_id", ""),
            signal_id=ctx_data.get("signal_id", ""),
            strategy_id=ctx_data.get("strategy_id", ""),
            portfolio_id=ctx_data.get("portfolio_id", ""),
            account_id=ctx_data.get("account_id", ""),
            policy_version=ctx_data.get("policy_version", ""),
            risk_version=ctx_data.get("risk_version", ""),
            governance_version=ctx_data.get("governance_version", ""),
            authority_version=ctx_data.get("authority_version", ""),
            approval_version=ctx_data.get("approval_version", ""),
            created_at=ctx_data.get("created_at", time.time()),
            metadata=ctx_data.get("metadata", {}),
        )

        # Rebuild request
        req_data = d.get("request", {})
        payload = req_data.get("payload", {})
        request = ControlRequest(
            request_id=req_data.get("request_id", ""),
            domain=req_data.get("domain", ""),
            context=context,
            payload=payload,
            created_at=req_data.get("created_at", time.time()),
            ttl_seconds=req_data.get("ttl_seconds", 60.0),
            metadata=req_data.get("metadata", {}),
        )

        contract = ControlContract(
            contract_id=d.get("contract_id", ""),
            contract_version=d.get("contract_version", "v1"),
            domain=d.get("domain", ""),
            request=request,
            context=context,
            created_at=d.get("created_at", time.time()),
            expires_at=d.get("expires_at"),
            metadata=d.get("metadata", {}),
            tags=d.get("tags", {}),
        )

        # Rebuild response
        if d.get("response"):
            rdata = d["response"]
            contract.response = ControlResponse(
                response_id=rdata.get("response_id", ""),
                domain=rdata.get("domain", ""),
                status=ControlResponseStatus[rdata["status"]] if rdata.get("status") else ControlResponseStatus.PASS,
                reason_code=ReasonCode[rdata["reason_code"]] if rdata.get("reason_code") else ReasonCode.RISK_CHECK_PASSED,
                reason=rdata.get("reason", ""),
                flow_id=rdata.get("flow_id", ""),
                request_id=rdata.get("request_id", ""),
                contract_id=rdata.get("contract_id", ""),
                timestamp=rdata.get("timestamp", time.time()),
                latency_ms=rdata.get("latency_ms", 0.0),
                metadata=rdata.get("metadata", {}),
            )

        # Rebuild constraints
        for cdata in d.get("constraints", []):
            constraint = ControlConstraint(
                constraint_id=cdata.get("constraint_id", ""),
                constraint_type=ConstraintType[cdata["constraint_type"]] if cdata.get("constraint_type") else ConstraintType.MAX_NOTIONAL,
                rule=ConstraintRule[cdata["rule"]] if cdata.get("rule") else ConstraintRule.MAX,
                numeric_value=cdata.get("numeric_value"),
                set_value=set(cdata["set_value"]) if cdata.get("set_value") else None,
                source=ConstraintSource[cdata["source"]] if cdata.get("source") else ConstraintSource.RISK,
                policy_version=cdata.get("policy_version", ""),
                rule_id=cdata.get("rule_id", ""),
                reason=cdata.get("reason", ""),
                created_at=cdata.get("created_at", time.time()),
                expires_at=cdata.get("expires_at"),
            )
            contract.constraints.append(constraint)

        # Rebuild evidence
        for edata in d.get("evidence", []):
            evidence = ControlEvidence(
                evidence_id=edata.get("evidence_id", ""),
                domain=edata.get("domain", ""),
                metrics=edata.get("metrics", {}),
                tags=edata.get("tags", {}),
                evaluated_at=edata.get("evaluated_at", time.time()),
            )
            contract.evidence.append(evidence)

        # Rebuild references
        for rdata in d.get("references", []):
            ref = ControlReference(
                reference_id=rdata.get("reference_id", ""),
                domain=rdata.get("domain", ""),
                parent_reference_id=rdata.get("parent_reference_id"),
                flow_id=rdata.get("flow_id", ""),
                decision_id=rdata.get("decision_id", ""),
                contract_id=rdata.get("contract_id", ""),
                created_at=rdata.get("created_at", time.time()),
                metadata=rdata.get("metadata", {}),
            )
            contract.references.append(ref)

        # Rebuild decision
        if d.get("decision"):
            ddata = d["decision"]
            decision = ControlDecision(
                decision_id=ddata.get("decision_id", ""),
                flow_id=ddata.get("flow_id", ""),
                status=DecisionStatus[ddata["status"]] if ddata.get("status") else DecisionStatus.PENDING,
                reason_code=ReasonCode[ddata["reason_code"]] if ddata.get("reason_code") else ReasonCode.RISK_CHECK_PASSED,
                reason=ddata.get("reason", ""),
                policy_version=ddata.get("policy_version", ""),
                decided_at=ddata.get("decided_at", time.time()),
                expires_at=ddata.get("expires_at"),
                metadata=ddata.get("metadata", {}),
            )
            contract.decision = decision

        return contract
