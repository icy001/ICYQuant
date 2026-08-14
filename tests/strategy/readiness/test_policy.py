"""Tests for the readiness policy model."""

from services.strategy.readiness.policy import ReadinessPolicy


def test_policy_defaults() -> None:
    policy = ReadinessPolicy()
    assert policy.require_runtime is True
    assert policy.require_market_data is True
    assert policy.require_configuration is True
    assert policy.require_risk is True
    assert policy.require_execution is True
    assert policy.allow_degraded is False


def test_policy_requires_maps_switches() -> None:
    policy = ReadinessPolicy()
    assert policy.requires("runtime") is True
    assert policy.requires("market_data") is True
    assert policy.requires("configuration") is True
    assert policy.requires("risk") is True
    assert policy.requires("execution") is True


def test_policy_lifecycle_cannot_be_disabled() -> None:
    policy = ReadinessPolicy()
    # There is no require_lifecycle switch; the lifecycle gate always holds.
    assert policy.requires("lifecycle") is True


def test_policy_unknown_check_defaults_to_required() -> None:
    policy = ReadinessPolicy()
    assert policy.requires("analytics") is True


def test_policy_can_disable_a_requirement() -> None:
    policy = ReadinessPolicy(require_risk=False)
    assert policy.requires("risk") is False
    assert policy.requires("runtime") is True


def test_policy_allow_degraded() -> None:
    policy = ReadinessPolicy(allow_degraded=True)
    assert policy.allow_degraded is True


def test_policy_is_frozen() -> None:
    policy = ReadinessPolicy()
    try:
        policy.allow_degraded = True
    except Exception:
        return
    raise AssertionError("ReadinessPolicy must be frozen")
