import pytest

from services.execution.domain.idempotency import (
    ExecutionIdempotencyKey,
)


def test_idempotency_key_creation():

    key = ExecutionIdempotencyKey(
        key="order-001:exec-001"
    )

    assert key.key == "order-001:exec-001"


def test_empty_idempotency_key_is_rejected():

    with pytest.raises(ValueError):
        ExecutionIdempotencyKey(key="")


def test_idempotency_key_is_immutable():

    key = ExecutionIdempotencyKey(
        key="order-001:exec-001"
    )

    with pytest.raises(Exception):
        key.key = "another-key"
