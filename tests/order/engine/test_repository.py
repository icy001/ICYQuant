"""Tests for the order repository boundary (Commit 33 Part 1.2)."""

from __future__ import annotations

import pytest

from services.order.domain.order_status import OrderStatus
from services.order.engine.repository import (
    InMemoryOrderRepository,
    OrderPersistenceError,
    OrderRepository,
)


def test_save_and_get_round_trip(repository: InMemoryOrderRepository, make_order):
    order = make_order()
    repository.save(order)
    assert repository.get(order.order_id) is order


def test_get_unknown_order_returns_none(repository: InMemoryOrderRepository):
    assert repository.get("ORD-DOES-NOT-EXIST") is None


def test_update_replaces_stored_order(repository: InMemoryOrderRepository, make_order):
    order = make_order()
    repository.save(order)

    updated = order.with_status(OrderStatus.SUBMITTED)
    repository.update(updated)

    assert repository.get(order.order_id) is updated


def test_update_unknown_order_raises(repository: InMemoryOrderRepository, make_order):
    with pytest.raises(OrderPersistenceError):
        repository.update(make_order())  # never saved


def test_fail_on_save(repository: InMemoryOrderRepository, make_order):
    repository.fail_on_save = True
    with pytest.raises(OrderPersistenceError):
        repository.save(make_order())


def test_fail_on_update(repository: InMemoryOrderRepository, make_order):
    order = make_order()
    repository.save(order)
    repository.fail_on_update = True

    with pytest.raises(OrderPersistenceError):
        repository.update(order.with_status(OrderStatus.SUBMITTED))


def test_in_memory_repository_satisfies_protocol(
    repository: InMemoryOrderRepository,
):
    assert isinstance(repository, OrderRepository)


def test_protocol_accepts_conforming_implementation():
    class FakeRepository:
        def save(self, order) -> None:
            pass

        def get(self, order_id):
            return None

        def update(self, order) -> None:
            pass

    assert isinstance(FakeRepository(), OrderRepository)


def test_protocol_rejects_missing_methods():
    class Incomplete:
        def save(self, order) -> None:
            pass

    assert not isinstance(Incomplete(), OrderRepository)
