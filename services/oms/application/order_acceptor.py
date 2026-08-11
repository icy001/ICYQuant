"""OrderAcceptor — the boundary between Admission and OMS.

The OrderAcceptor has one responsibility:

    Verify that the Admission Certificate is valid, then create
    an Order in the OMS.

OMS does NOT re-run Risk / Governance / Authority / Approval.
It only verifies the Certificate produced by the Control Plane.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from services.oms.domain.order import Order
from services.oms.domain.order_id import OrderId
from services.oms.domain.order_side import OrderSide
from services.oms.domain.order_status import OrderStatus
from services.oms.domain.order_type import OrderType
from services.oms.domain.time_in_force import TimeInForce
from services.oms.domain.order_lifecycle import (
    OrderLifecycleEvent,
    LifecycleEventType,
)
from services.oms.errors.order_errors import (
    OrderNotAcceptedError,
    OrderCertificateError,
    OrderIdempotencyError,
)


# ── Certificate verification result ─────────────────


class CertificateVerification:
    """Result of verifying an admission certificate."""

    def __init__(self, valid: bool, reason: str = "",
                 certificate_id: str = "",
                 scope: Optional[Dict[str, Any]] = None) -> None:
        self.valid = valid
        self.reason = reason
        self.certificate_id = certificate_id
        self.scope = scope or {}

    @classmethod
    def ok(cls, certificate_id: str,
           scope: Optional[Dict[str, Any]] = None) -> "CertificateVerification":
        return cls(True, certificate_id=certificate_id, scope=scope or {})

    @classmethod
    def fail(cls, reason: str,
             certificate_id: str = "") -> "CertificateVerification":
        return cls(False, reason=reason, certificate_id=certificate_id)


# ── Admission request ────────────────────────────────


class AdmissionRequest:
    """A request to admit an order into the OMS.

    Carries everything the OMS needs to verify the certificate and
    create the Order, without re-running any control logic.
    """

    def __init__(self,
                 certificate_id: str,
                 flow_id: str,
                 lineage_id: str,
                 decision_id: str,
                 order_intent_id: str,
                 client_order_id: str,
                 symbol: str,
                 side: OrderSide,
                 order_type: OrderType,
                 quantity: float,
                 time_in_force: TimeInForce = TimeInForce.DAY,
                 limit_price: float = 0.0,
                 stop_price: float = 0.0,
                 account_id: str = "",
                 strategy_id: str = "",
                 parent_order_id: str = "",
                 root_order_id: str = "",
                 expires_at: Optional[float] = None,
                 metadata: Optional[Dict[str, Any]] = None,
                 intent_hash: str = "",
                 certificate_fingerprint: str = "") -> None:
        self.certificate_id = certificate_id
        self.flow_id = flow_id
        self.lineage_id = lineage_id
        self.decision_id = decision_id
        self.order_intent_id = order_intent_id
        self.client_order_id = client_order_id
        self.symbol = symbol
        self.side = side
        self.order_type = order_type
        self.quantity = quantity
        self.time_in_force = time_in_force
        self.limit_price = limit_price
        self.stop_price = stop_price
        self.account_id = account_id
        self.strategy_id = strategy_id
        self.parent_order_id = parent_order_id
        self.root_order_id = root_order_id
        self.expires_at = expires_at
        self.metadata = dict(metadata or {})
        self.intent_hash = intent_hash
        self.certificate_fingerprint = certificate_fingerprint


# ── Acceptor ─────────────────────────────────────────


class OrderAcceptor:
    """Boundary object: Admission Certificate → OMS Order.

    The acceptor runs a verification pipeline:

        Receive Admission
             ↓
        Verify Certificate
             ↓
        Verify Intent Hash
             ↓
        Verify Scope
             ↓
        Verify Constraints
             ↓
        Create Order

    Any failure raises OrderNotAcceptedError.
    """

    def __init__(self,
                 certificate_verifier: Optional[Callable[[str], CertificateVerification]] = None,
                 intent_verifier: Optional[Callable[[AdmissionRequest], bool]] = None,
                 idempotency_check: Optional[Callable[[str], Optional[Order]]] = None,
                 scope_validator: Optional[Callable[[AdmissionRequest, Dict[str, Any]], bool]] = None,
                 actor: str = "oms-acceptor",
                 actor_type: str = "OMS") -> None:
        self._verify_certificate = certificate_verifier or _default_cert_verifier
        self._verify_intent = intent_verifier or _default_intent_verifier
        self._check_idempotency = idempotency_check or (lambda _: None)
        self._validate_scope = scope_validator or (lambda req, scope: True)
        self.actor = actor
        self.actor_type = actor_type

    # ── Public API ─────────────────────────────────

    def accept(self, request: AdmissionRequest) -> Order:
        """Accept an admission request and create an OMS Order.

        Raises:
            OrderIdempotencyError: duplicate client_order_id.
            OrderNotAcceptedError: any verification failure.
        """
        # 1. Idempotency — return existing order if duplicate
        existing = self._check_idempotency(request.client_order_id)
        if existing is not None:
            raise OrderIdempotencyError(
                request.client_order_id,
                existing_order_id=existing.order_id.order_id,
            )

        # 2. Verify certificate
        cert_result = self._verify_certificate(request.certificate_id)
        if not cert_result.valid:
            raise OrderCertificateError(
                certificate_id=request.certificate_id,
                reason=cert_result.reason,
            )

        # 3. Verify intent hash
        if not self._verify_intent(request):
            raise OrderNotAcceptedError(
                request.client_order_id,
                reason="Intent hash mismatch",
            )

        # 4. Verify scope
        if not self._validate_scope(request, cert_result.scope):
            raise OrderNotAcceptedError(
                request.client_order_id,
                reason="Certificate scope violation",
            )

        # 5. Verify constraints
        if not request.certificate_id:
            raise OrderNotAcceptedError(
                request.client_order_id,
                reason="Missing certificate_id",
            )
        if not request.lineage_id:
            raise OrderNotAcceptedError(
                request.client_order_id,
                reason="Missing lineage_id",
            )
        if request.quantity <= 0:
            raise OrderNotAcceptedError(
                request.client_order_id,
                reason="Quantity must be positive",
            )
        if request.order_type.requires_price and request.limit_price <= 0:
            raise OrderNotAcceptedError(
                request.client_order_id,
                reason="Limit order requires positive limit_price",
            )

        # 6. Create order
        order = Order.create(
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            time_in_force=request.time_in_force,
            limit_price=request.limit_price,
            stop_price=request.stop_price,
            flow_id=request.flow_id,
            lineage_id=request.lineage_id,
            decision_id=request.decision_id,
            order_intent_id=request.order_intent_id,
            certificate_id=request.certificate_id,
            account_id=request.account_id,
            strategy_id=request.strategy_id,
            client_order_id=request.client_order_id,
            parent_order_id=request.parent_order_id,
            root_order_id=request.root_order_id,
            expires_at=request.expires_at,
            metadata=request.metadata,
        )

        # 7. Emit ORDER_ACCEPTED event
        accept_event = OrderLifecycleEvent.create(
            event_type=LifecycleEventType.ORDER_ACCEPTED,
            order_id=order.order_id.order_id,
            previous_status=OrderStatus.RECEIVED,
            lineage_id=order.lineage_id,
            certificate_id=order.certificate_id,
            actor=self.actor,
            actor_type=self.actor_type,
            reason="Certificate verified",
        )
        order.apply_event(accept_event)

        return order


# ── Default verifiers (permissive — override in production) ──


def _default_cert_verifier(certificate_id: str) -> CertificateVerification:
    if not certificate_id:
        return CertificateVerification.fail("Empty certificate_id")
    return CertificateVerification.ok(certificate_id)


def _default_intent_verifier(request: AdmissionRequest) -> bool:
    return True
