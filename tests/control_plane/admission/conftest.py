"""Shared fixtures for the Order Admission test suite (spec sections 8/17)."""
from __future__ import annotations

import pytest

from services.control_plane.admission.risk import RiskDecision, RiskResult
from services.control_plane.controls.control_type import ControlType
from services.control_plane.controls.registry import ControlRegistry
from services.control_plane.controls.scope import ControlScope
from services.control_plane.gateway.context import ControlContext
from services.control_plane.gateway.gateway import (
    InstitutionalControlGateway,
)
from services.control_plane.admission.request import OrderAdmissionRequest


class FakeRiskEngine:
    """Duck-typed risk engine returning a configurable RiskDecision."""

    def __init__(
        self,
        decision="APPROVED",
        reason="",
        risk_score=None,
    ):
        self._decision = RiskDecision(decision)
        self.reason = reason
        self.risk_score = risk_score
        self.calls: list = []

    def evaluate(self, request):
        self.calls.append(request)
        return RiskResult(
            decision=self._decision,
            reason=self.reason,
            risk_score=self.risk_score,
        )

    @property
    def call_count(self) -> int:
        return len(self.calls)


class BrokenRiskEngine:
    """A risk engine whose backend is unavailable."""

    def evaluate(self, request):
        raise RuntimeError("risk backend unavailable")


class BrokenGateway:
    """A control gateway whose backend is unavailable."""

    def evaluate(self, context, *, is_new_order=True):
        raise RuntimeError("gateway unavailable")


@pytest.fixture
def risk_engine():
    return FakeRiskEngine()


@pytest.fixture
def registry():
    return ControlRegistry()


@pytest.fixture
def control_gateway(registry):
    return InstitutionalControlGateway(registry)


@pytest.fixture
def position_provider():
    """Default position book: NVDA holds +100."""
    return lambda request: 100.0


@pytest.fixture
def admission_service(risk_engine, control_gateway, position_provider):
    from services.control_plane.admission.service import (
        OrderAdmissionService,
    )

    return OrderAdmissionService(
        risk_engine=risk_engine,
        control_gateway=control_gateway,
        position_provider=position_provider,
    )


@pytest.fixture
def admission_request():
    # Default side is SELL (position-reducing at +100): reduce-only scenarios
    # in spec section 17 stay consistent with the position-aware validator.
    return OrderAdmissionRequest(
        context=ControlContext(
            account_id="ACC001",
            strategy_id="alpha_nvda",
            symbol="NVDA",
            venue="NASDAQ",
        ),
        symbol="NVDA",
        side="SELL",
        quantity=100,
        order_type="LIMIT",
    )


def register_control(
    registry,
    control_type: ControlType,
    scope: ControlScope,
    target: str,
    reason: str = "test control",
):
    """Register a ControlAction on the gateway registry."""
    from services.control_plane.controls.control import ControlAction

    registry.register(
        ControlAction(
            control_type=control_type,
            scope=scope,
            target=target,
            reason=reason,
        )
    )
