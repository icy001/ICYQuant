"""CertificateBuilder — assembles PreTradeControlCertificate from control context.

IMPORTANT: The CertificateBuilder can ONLY assemble evidence into a certificate.
It CANNOT approve orders, override gate decisions, or weaken constraints.
It is purely an assembly/recording component — not an approval engine.

Input: ControlContext + Risk/Governance/Authority/Approval decisions + OrderIntent
Output: PreTradeControlCertificate (sealed)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .pre_trade_certificate import PreTradeControlCertificate
from .certificate_scope import CertificateScope, ConsumptionMode, ScopeGranularity
from .certificate_claim import CertificateClaim, ClaimType
from .certificate_evidence import CertificateEvidence, EvidenceKind


@dataclass
class CertificateBuilder:
    """Assembles a PreTradeControlCertificate from validated control evidence.

    Usage:
        builder = CertificateBuilder()
        builder.with_flow_id("FLOW-001")
        builder.with_order_intent(intent)
        builder.with_risk_decision(passed=True, ...)
        builder.with_governance_decision(passed=True, ...)
        builder.with_authority_decision(passed=True, ...)
        builder.with_approval_decision(passed=True, ...)
        cert = builder.build()
        cert.seal()
    """

    # ── Identity ──────────────────────────────────────────────
    _flow_id: str = ""
    _decision_id: str = ""
    _signal_id: str = ""
    _strategy_id: str = ""

    # ── Order context ─────────────────────────────────────────
    _order_intent_id: str = ""
    _intent_hash: str = ""
    _order_id: str = ""
    _account_id: str = ""
    _portfolio_id: str = ""

    # ── Scope ─────────────────────────────────────────────────
    _symbol: str = ""
    _side: str = ""
    _venue: str = ""
    _order_type: str = ""
    _quantity: float = 0.0
    _limit_price: Optional[float] = None
    _max_notional: Optional[float] = None
    _max_leverage: Optional[float] = None
    _allowed_order_types: List[str] = field(default_factory=list)

    # ── Gate decision flags (PASS = True, FAIL = False) ──────
    _risk_passed: bool = False
    _governance_passed: bool = False
    _authority_passed: bool = False
    _approval_passed: bool = False

    # ── Gate detail ───────────────────────────────────────────
    _risk_detail: Dict[str, Any] = field(default_factory=dict)
    _governance_state: str = ""
    _authority_id: str = ""
    _authority_limit: float = 0.0
    _approval_id: str = ""
    _approval_status: str = ""
    _approval_amount: float = 0.0

    # ── Evidence ──────────────────────────────────────────────
    _evidence_list: List[CertificateEvidence] = field(default_factory=list)

    # ── Policy versions ───────────────────────────────────────
    _policy_versions: Dict[str, str] = field(default_factory=dict)

    # ── Effective constraints ─────────────────────────────────
    _effective_constraints: Dict[str, Any] = field(default_factory=dict)

    # ── Expiry ────────────────────────────────────────────────
    _expires_at: Optional[float] = None
    _ttl_seconds: float = 300.0  # default 5 minute TTL

    # ── Fluent builder methods ────────────────────────────────

    def with_flow_id(self, flow_id: str) -> "CertificateBuilder":
        self._flow_id = flow_id
        return self

    def with_decision_id(self, decision_id: str) -> "CertificateBuilder":
        self._decision_id = decision_id
        return self

    def with_signal_id(self, signal_id: str) -> "CertificateBuilder":
        self._signal_id = signal_id
        return self

    def with_strategy_id(self, strategy_id: str) -> "CertificateBuilder":
        self._strategy_id = strategy_id
        return self

    def with_order_intent(
        self,
        intent_id: str,
        intent_hash: str,
        account_id: str = "",
        portfolio_id: str = "",
        order_id: str = "",
    ) -> "CertificateBuilder":
        """Bind an OrderIntent to the certificate."""
        self._order_intent_id = intent_id
        self._intent_hash = intent_hash
        self._account_id = account_id
        self._portfolio_id = portfolio_id
        self._order_id = order_id
        return self

    def with_symbol(self, symbol: str) -> "CertificateBuilder":
        self._symbol = symbol
        return self

    def with_side(self, side: str) -> "CertificateBuilder":
        self._side = side
        return self

    def with_venue(self, venue: str) -> "CertificateBuilder":
        self._venue = venue
        return self

    def with_order_type(self, order_type: str) -> "CertificateBuilder":
        self._order_type = order_type
        return self

    def with_quantity(self, quantity: float) -> "CertificateBuilder":
        self._quantity = quantity
        return self

    def with_limit_price(self, price: Optional[float]) -> "CertificateBuilder":
        self._limit_price = price
        return self

    def with_max_notional(self, notional: Optional[float]) -> "CertificateBuilder":
        self._max_notional = notional
        return self

    def with_max_leverage(self, leverage: Optional[float]) -> "CertificateBuilder":
        self._max_leverage = leverage
        return self

    def with_allowed_order_types(
        self, types: List[str]
    ) -> "CertificateBuilder":
        self._allowed_order_types = types
        return self

    def with_risk_decision(
        self,
        passed: bool,
        gate_id: str = "",
        policy_version: str = "",
        detail: Optional[Dict[str, Any]] = None,
    ) -> "CertificateBuilder":
        """Record risk gate decision."""
        self._risk_passed = passed
        self._risk_detail = detail or {}
        if policy_version:
            self._policy_versions["risk"] = policy_version
        self._evidence_list.append(
            CertificateEvidence.risk_evidence(
                gate_id=gate_id, source_version=policy_version,
                **(detail or {}),
            )
        )
        return self

    def with_governance_decision(
        self,
        passed: bool,
        state: str = "NORMAL",
        gate_id: str = "",
        policy_version: str = "",
    ) -> "CertificateBuilder":
        """Record governance gate decision."""
        self._governance_passed = passed
        self._governance_state = state
        if policy_version:
            self._policy_versions["governance"] = policy_version
        self._evidence_list.append(
            CertificateEvidence.governance_evidence(
                governance_state=state,
                gate_id=gate_id,
                source_version=policy_version,
            )
        )
        return self

    def with_authority_decision(
        self,
        passed: bool,
        authority_id: str = "",
        limit: float = 0.0,
        policy_version: str = "",
    ) -> "CertificateBuilder":
        """Record authority gate decision."""
        self._authority_passed = passed
        self._authority_id = authority_id
        self._authority_limit = limit
        if policy_version:
            self._policy_versions["authority"] = policy_version
        self._evidence_list.append(
            CertificateEvidence.authority_evidence(
                authority_id=authority_id,
                authority_limit=limit,
                requested=self._quantity * (self._limit_price or 0),
                gate_id=authority_id,
                source_version=policy_version,
            )
        )
        return self

    def with_approval_decision(
        self,
        passed: bool,
        approval_id: str = "",
        status: str = "",
        amount: float = 0.0,
        policy_version: str = "",
    ) -> "CertificateBuilder":
        """Record approval gate decision."""
        self._approval_passed = passed
        self._approval_id = approval_id
        self._approval_status = status
        self._approval_amount = amount
        if policy_version:
            self._policy_versions["approval"] = policy_version
        self._evidence_list.append(
            CertificateEvidence.approval_evidence(
                approval_id=approval_id,
                status=status,
                approved_amount=amount,
                gate_id=approval_id,
                source_version=policy_version,
            )
        )
        return self

    def with_effective_constraints(
        self, constraints: Dict[str, Any]
    ) -> "CertificateBuilder":
        """Record effective constraints at issuance time."""
        self._effective_constraints = dict(constraints)
        self._evidence_list.append(
            CertificateEvidence.constraints_evidence(
                constraints=self._effective_constraints
            )
        )
        return self

    def with_policy_versions(
        self, versions: Dict[str, str]
    ) -> "CertificateBuilder":
        """Set all policy versions at once."""
        self._policy_versions.update(versions)
        return self

    def with_ttl(self, ttl_seconds: float) -> "CertificateBuilder":
        """Set certificate time-to-live."""
        self._ttl_seconds = ttl_seconds
        return self

    def with_scope_consumption_mode(
        self, mode: ConsumptionMode
    ) -> "CertificateBuilder":
        self._scope_consumption_mode = mode
        return self

    _scope_consumption_mode: ConsumptionMode = ConsumptionMode.ONE_TIME

    # ── Build ─────────────────────────────────────────────────

    def build(self) -> PreTradeControlCertificate:
        """Assemble and return a PreTradeControlCertificate.

        IMPORTANT: This only assembles evidence. It does NOT approve orders.
        Caller must have already validated all gate decisions before building.
        """
        now = time.time()
        expires = self._expires_at or (now + self._ttl_seconds)

        # ── Build scope ───────────────────────────────────────
        scope = CertificateScope(
            account_id=self._account_id,
            portfolio_id=self._portfolio_id,
            strategy_id=self._strategy_id,
            symbol=self._symbol.upper() if self._symbol else "",
            venue=self._venue.upper() if self._venue else "",
            side=self._side.upper() if self._side else "",
            order_type=self._order_type.upper() if self._order_type else "",
            max_quantity=self._quantity if self._quantity > 0 else None,
            max_notional=self._max_notional,
            max_leverage=self._max_leverage,
            allowed_order_types=list(self._allowed_order_types),
            granularity=ScopeGranularity.ORDER,
            consumption_mode=self._scope_consumption_mode,
            issued_at=now,
            expires_at=expires,
        )

        # ── Build claims ──────────────────────────────────────
        risk_claim = CertificateClaim.risk_claim(
            passed=self._risk_passed,
            gate_id="risk_gate",
            policy_version=self._policy_versions.get("risk", ""),
            detail=self._risk_detail,
        )

        gov_claim = CertificateClaim.governance_claim(
            passed=self._governance_passed,
            state=self._governance_state,
            gate_id="governance_gate",
            policy_version=self._policy_versions.get("governance", ""),
        )

        auth_claim = CertificateClaim.authority_claim(
            passed=self._authority_passed,
            authority_id=self._authority_id,
            limit=self._authority_limit,
            policy_version=self._policy_versions.get("authority", ""),
        )

        appr_claim = CertificateClaim.approval_claim(
            passed=self._approval_passed,
            approval_id=self._approval_id,
            status=self._approval_status,
            amount=self._approval_amount,
            policy_version=self._policy_versions.get("approval", ""),
        )

        # ── Build certificate ─────────────────────────────────
        cert = PreTradeControlCertificate(
            flow_id=self._flow_id,
            decision_id=self._decision_id,
            signal_id=self._signal_id,
            strategy_id=self._strategy_id,
            order_intent_id=self._order_intent_id,
            order_id=self._order_id,
            account_id=self._account_id,
            portfolio_id=self._portfolio_id,
            intent_hash=self._intent_hash,
            scope=scope,
            risk_claim=risk_claim,
            governance_claim=gov_claim,
            authority_claim=auth_claim,
            approval_claim=appr_claim,
            evidence=list(self._evidence_list),
            policy_versions=dict(self._policy_versions),
            effective_constraints=dict(self._effective_constraints),
            issued_at=now,
            expires_at=expires,
        )

        return cert

    def build_and_seal(self) -> PreTradeControlCertificate:
        """Build the certificate and seal it (fingerprint + signature + activate).

        This is the recommended one-step method for normal usage.
        """
        cert = self.build()
        cert.seal()
        return cert
