from uuid import uuid4

from services.order.idempotency import IdempotencyRegistry


def test_registry():
    registry = IdempotencyRegistry()

    order_id = uuid4()

    registry.register("ABC123", order_id)

    assert registry.exists("ABC123")

    assert registry.get("ABC123") == order_id


def test_nonexistent_client_order_id():
    registry = IdempotencyRegistry()

    assert not registry.exists("NONEXISTENT")

    assert registry.get("NONEXISTENT") is None