"""OrderAdmission — the institutional order admission boundary orchestrator.

This is the central orchestrator that gates all orders before they enter OMS.
Pipeline: RECEIVE → VALIDATE → AUTHORIZE → NORMALIZE → DEDUPE → RESERVE → ADMIT

No Order enters OMS without passing through this boundary.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .order_intent import OrderIntent
from .order_constraints import OrderConstraints
from .order_fingerprint import OrderFingerprint
from .order_certificate import OrderCertificate

from .admission_context import AdmissionContext
from .admission_request import AdmissionRequest
from .admission_result import AdmissionResult, AdmissionResultStatus
from .admission_state import AdmissionState
from .admission_policy import AdmissionPolicy, AdmissionPolicyLevel

from .admission_validator import AdmissionValidator
from .admission_authorizer import AdmissionAuthorizer, AuthorizationReport
from .admission_normalizer import AdmissionNormalizer
from .admission_deduplicator import AdmissionDeduplicator
from .admission_reservation import AdmissionReservation
from .admission_gate import AdmissionGate
from .admission_registry import AdmissionRegistry
from .admission_metrics import AdmissionMetrics


@dataclass
class OrderAdmission:
    """Institutional order admission boundary.

    Orchestrates the full pipeline:
    RECEIVE → VALIDATE → AUTHORIZE → NORMALIZE → DEDUPE → RESERVE → ADMIT

    This is the final governance boundary between the Decision world
    and the Execution world. No order bypasses this layer.
    """

    # Injected services
    validator: AdmissionValidator = field(default_factory=AdmissionValidator)
    authorizer: AdmissionAuthorizer = field(default_factory=AdmissionAuthorizer)
    normalizer: AdmissionNormalizer = field(default_factory=AdmissionNormalizer)
    deduplicator: AdmissionDeduplicator = field(default_factory=AdmissionDeduplicator)
    reservation: AdmissionReservation = field(default_factory=AdmissionReservation)
    gate: AdmissionGate = field(default_factory=AdmissionGate)
    registry: AdmissionRegistry = field(default_factory=AdmissionRegistry)
    metrics: AdmissionMetrics = field(default_factory=AdmissionMetrics)

    # Policy
    policy: AdmissionPolicy = field(default_factory=AdmissionPolicy.standard)

    def admit(self, request: AdmissionRequest) -> AdmissionResult:
        """Run the full admission pipeline.

        Returns AdmissionResult indicating ADMITTED, REJECTED, BLOCKED,
        DUPLICATE, EXPIRED, or RESERVATION_FAILED.
        """
        self.metrics.record_received()

        if request.intent is None:
            return self._fail("MISSING_INTENT", "No OrderIntent in request")

        intent = request.intent
        flow_id = intent.flow_id

        # ── Stage 0: RECEIVED ─────────────────────────────────
        ctx = AdmissionContext.from_intent(
            intent_id=intent.intent_id,
            flow_id=flow_id,
            decision_id=intent.decision_id,
            strategy_id=intent.strategy_id,
            portfolio_id=intent.portfolio_id,
            account_id=intent.account_id,
        )
        ctx = ctx.with_approval(
            request.approval_id, request.approval_policy_version
        ).with_authority(
            request.authority_id, request.authority_limit
        ).with_governance_state(
            request.governance_state
        ).with_versions(
            policy=request.policy_version,
            risk=request.risk_version,
            governance=request.governance_version,
            authority=request.authority_version,
            approval=request.approval_version,
        )
        # ctx already starts in RECEIVED state

        # ── Stage 1: VALIDATE ─────────────────────────────────
        t0 = time.time()
        ctx.transition_to(AdmissionState.VALIDATING)

        validation = self.validator.validate(request)
        if not validation.valid:
            self.metrics.record_rejected("VALIDATION_FAILED")
            self.metrics.record_stage_latency("validate", time.time() - t0)
            return self._reject(
                ctx, "VALIDATION_FAILED",
                f"Validation failed: {len(validation.errors)} error(s)",
                errors=[e.code for e in validation.errors],
            )

        self.metrics.record_check("validation", True)
        self.metrics.record_stage_latency("validate", time.time() - t0)
        ctx.transition_to(AdmissionState.VALIDATED)

        # ── Stage 2: AUTHORIZE ────────────────────────────────
        t0 = time.time()
        ctx.transition_to(AdmissionState.AUTHORIZING)

        auth_report = self.authorizer.authorize(request)
        for check in auth_report.checks:
            self.metrics.record_check(check.name, check.passed)

        if not auth_report.authorized:
            failed = next((c for c in auth_report.checks if not c.passed), None)
            code = failed.code if failed else "AUTHORIZATION_FAILED"
            self.metrics.record_blocked(code)
            self.metrics.record_stage_latency("authorize", time.time() - t0)
            return self._block(ctx, code, failed.message if failed else "Authorization failed")

        self.metrics.record_stage_latency("authorize", time.time() - t0)
        ctx.transition_to(AdmissionState.AUTHORIZED)

        # ── Stage 3: NORMALIZE ────────────────────────────────
        t0 = time.time()
        ctx.transition_to(AdmissionState.NORMALIZING)

        norm_result = self.normalizer.normalize(intent)
        if not norm_result.normalized:
            self.metrics.record_rejected("NORMALIZATION_FAILED")
            self.metrics.record_stage_latency("normalize", time.time() - t0)
            return self._reject(
                ctx, "NORMALIZATION_FAILED",
                "Normalization failed",
                errors=norm_result.errors,
            )

        self.metrics.record_stage_latency("normalize", time.time() - t0)
        ctx.transition_to(AdmissionState.NORMALIZED)

        # ── Stage 4: DEDUPLICATE ──────────────────────────────
        if self.policy.deduplication_enabled:
            t0 = time.time()
            dedup = self.deduplicator.check_duplicate(
                intent, request.idempotency_key
            )
            if dedup.is_duplicate:
                self.metrics.record_duplicate()
                self.metrics.record_stage_latency("deduplicate", time.time() - t0)
                previous_result = self.deduplicator.get_idempotency_result(
                    request.idempotency_key
                )
                return AdmissionResult.make_duplicate(
                    flow_id=flow_id,
                    intent_id=intent.intent_id,
                    original_order_id=(
                        previous_result.get("order_id", "")
                        if previous_result else ""
                    ),
                )
            self.metrics.record_stage_latency("deduplicate", time.time() - t0)

        # ── Stage 5: RESERVE ──────────────────────────────────
        order_id = f"ORDER-{uuid.uuid4().hex[:12].upper()}"
        ctx = ctx.with_order_id(order_id)

        if self.policy.reservation_required:
            t0 = time.time()
            ctx.transition_to(AdmissionState.RESERVING)

            resv_result = self.reservation.reserve(intent, order_id)
            if not resv_result.success:
                self.metrics.record_reservation_failed(resv_result.code)
                self.metrics.record_stage_latency("reserve", time.time() - t0)
                return AdmissionResult.make_reservation_failed(
                    code=resv_result.code,
                    message=resv_result.message,
                    flow_id=flow_id,
                    intent_id=intent.intent_id,
                )

            self.metrics.record_stage_latency("reserve", time.time() - t0)
            ctx.transition_to(AdmissionState.RESERVED)

        # ── Stage 6: ADMIT ────────────────────────────────────
        ctx.transition_to(AdmissionState.ADMITTED)

        # Build constraints from request
        constraints = self._build_constraints(request)

        # Issue certificate
        fp = OrderFingerprint.compute(intent)
        result = AdmissionResult.make_admitted(
            flow_id=flow_id,
            intent_id=intent.intent_id,
            order_id=order_id,
            certificate_id="",
        )

        if self.policy.certificate_required:
            certificate = self.gate.issue_certificate(
                intent=intent,
                constraints=constraints,
                result=result,
                context=ctx,
                fingerprint=fp.fingerprint,
            )
            result.certificate_id = certificate.certificate_id
        else:
            certificate = None

        # Store idempotency result
        if request.idempotency_key:
            self.deduplicator.store_idempotency_result(
                request.idempotency_key, result
            )

        # Register
        self.registry.register(flow_id, intent.intent_id, result, certificate)
        self.metrics.record_admitted()

        return result

    def _build_constraints(self, request: AdmissionRequest) -> OrderConstraints:
        """Build effective constraints from upstream gate results."""
        constraints = OrderConstraints()

        # Risk constraints
        if request.risk_passed:
            constraints.with_max_exposure(1.0, source="RISK")

        # Governance constraints
        if request.governance_passed:
            allowed_types = {"LIMIT", "MARKET"}
            constraints.with_allowed_order_types(allowed_types, source="GOVERNANCE")

        # Authority constraints
        if request.authority_limit is not None:
            constraints.with_max_notional(request.authority_limit, source="AUTHORITY")

        # Approval constraints
        if request.approval_amount is not None:
            constraints.with_max_notional(request.approval_amount, source="APPROVAL")

        if request.approval_expiry is not None:
            constraints.with_expiry(request.approval_expiry, source="APPROVAL")

        return constraints

    def _reject(
        self,
        ctx: AdmissionContext,
        code: str,
        message: str,
        errors: Optional[list] = None,
    ) -> AdmissionResult:
        ctx.set_error(code, message)
        result = AdmissionResult.make_rejected(
            code=code,
            message=message,
            flow_id=ctx.flow_id,
            intent_id=ctx.intent_id,
            errors=errors,
        )
        self.registry.register(ctx.flow_id, ctx.intent_id, result)
        return result

    def _block(
        self, ctx: AdmissionContext, code: str, message: str
    ) -> AdmissionResult:
        ctx.set_error(code, message)
        result = AdmissionResult.make_blocked(
            code=code,
            message=message,
            flow_id=ctx.flow_id,
            intent_id=ctx.intent_id,
        )
        self.registry.register(ctx.flow_id, ctx.intent_id, result)
        return result

    def _fail(self, code: str, message: str) -> AdmissionResult:
        self.metrics.record_rejected(code)
        return AdmissionResult.make_rejected(code=code, message=message)

    def reset(self) -> None:
        """Reset all state for testing."""
        self.deduplicator.reset()
        self.reservation.reset()
        self.registry.reset()
        self.metrics.reset()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy": self.policy.to_dict(),
            "registry": self.registry.to_dict(),
            "metrics": self.metrics.to_dict(),
        }

    def __repr__(self) -> str:
        return (
            f"OrderAdmission(policy={self.policy.level.label}, "
            f"metrics={self.metrics})"
        )
