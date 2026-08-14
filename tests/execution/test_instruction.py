import pytest

from services.execution.domain.instruction import (
    ExecutionInstruction,
    ExecutionPolicy,
)


def test_default_execution_policy():

    policy = ExecutionPolicy()

    assert (
        policy.instruction
        == ExecutionInstruction.IMMEDIATE
    )

    assert policy.allow_partial_fill is True


def test_negative_slippage_is_invalid():

    policy = ExecutionPolicy(
        max_slippage_bps=-1,
    )

    with pytest.raises(ValueError):
        policy.validate()


def test_timeout_must_be_positive():

    policy = ExecutionPolicy(
        timeout_seconds=0,
    )

    with pytest.raises(ValueError):
        policy.validate()


def test_configured_policy_is_valid():

    policy = ExecutionPolicy(
        instruction=ExecutionInstruction.TWAP,
        max_slippage_bps=25,
        timeout_seconds=30,
        allow_partial_fill=False,
    )

    policy.validate()

    assert policy.instruction == ExecutionInstruction.TWAP
    assert policy.max_slippage_bps == 25
    assert policy.timeout_seconds == 30
    assert policy.allow_partial_fill is False


def test_policy_is_immutable():

    policy = ExecutionPolicy()

    with pytest.raises(Exception):
        policy.timeout_seconds = 10
