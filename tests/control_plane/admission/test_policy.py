"""Tests for AdmissionPolicy (spec section 5)."""
from __future__ import annotations

from services.control_plane.admission.policy import AdmissionPolicy


def test_default_policy_is_strict():
    policy = AdmissionPolicy()

    assert policy.require_risk_approval is True
    assert policy.require_control_approval is True
    assert policy.allow_reduce_only is True
    assert policy.reject_on_gateway_failure is True
    assert policy.reject_zero_quantity is True
    assert policy.reject_negative_quantity is True


def test_policy_can_be_relaxed():
    policy = AdmissionPolicy(
        require_risk_approval=False,
        require_control_approval=False,
        allow_reduce_only=False,
        reject_on_gateway_failure=False,
        reject_zero_quantity=False,
        reject_negative_quantity=False,
    )

    assert policy.require_risk_approval is False
    assert policy.allow_reduce_only is False
    assert policy.reject_on_gateway_failure is False


def test_policy_is_frozen():
    import pytest
    from dataclasses import FrozenInstanceError

    policy = AdmissionPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.allow_reduce_only = False  # type: ignore[misc]
