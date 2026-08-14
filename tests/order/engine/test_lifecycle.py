"""Tests for the order lifecycle service (Commit 33 Part 1.2)."""

from __future__ import annotations

from datetime import datetime

import pytest

from services.order.domain.order_state import InvalidOrderStateTransition
from services.order.domain.order_status import OrderStatus
from services.order.domain.time_in_force import TimeInForce
from services.order.engine.lifecycle import OrderLifecycle
from services.order.engine.validator import OrderValidationError


def test_submit_moves_created_to_pending_submit(
    lifecycle: OrderLifecycle, make_order
):
    updated = lifecycle.submit(make_order(status=OrderStatus.CREATED))
    assert updated.status is OrderStatus.PENDING_SUBMIT


def test_submit_is_idempotent(lifecycle: OrderLifecycle, make_order):
    order = make_order(status=OrderStatus.PENDING_SUBMIT)
    assert lifecycle.submit(order) is order


def test_accept_moves_submitted_to_accepted(lifecycle: OrderLifecycle, make_order):
    updated = lifecycle.accept(make_order(status=OrderStatus.SUBMITTED))
    assert updated.status is OrderStatus.ACCEPTED


def test_accept_is_idempotent(lifecycle: OrderLifecycle, make_order):
    order = make_order(status=OrderStatus.ACCEPTED)
    assert lifecycle.accept(order) is order


def test_reject_records_reason(lifecycle: OrderLifecycle, make_order):
    updated = lifecycle.reject(
        make_order(status=OrderStatus.SUBMITTED),
        "BROKER_REJECTED",
    )
    assert updated.status is OrderStatus.REJECTED
    assert updated.reject_reason == "BROKER_REJECTED"


def test_reject_is_idempotent(lifecycle: OrderLifecycle, make_order):
    order = make_order(status=OrderStatus.REJECTED)
    assert lifecycle.reject(order, "BROKER_REJECTED") is order


def test_cancel_moves_accepted_to_cancel_pending(
    lifecycle: OrderLifecycle, make_order
):
    updated = lifecycle.cancel(make_order(status=OrderStatus.ACCEPTED))
    assert updated.status is OrderStatus.CANCEL_PENDING


def test_cancel_from_partially_filled_allowed(lifecycle: OrderLifecycle, make_order):
    # Spec #23: a partially filled order can still request a cancellation.
    updated = lifecycle.cancel(make_order(status=OrderStatus.PARTIALLY_FILLED))
    assert updated.status is OrderStatus.CANCEL_PENDING


def test_cancel_is_idempotent(lifecycle: OrderLifecycle, make_order):
    order = make_order(status=OrderStatus.CANCEL_PENDING)
    assert lifecycle.cancel(order) is order


def test_cancel_is_two_phase(lifecycle: OrderLifecycle, make_order):
    # Spec #22: ACCEPTED -> CANCEL_PENDING only; CANCELLED comes later.
    updated = lifecycle.cancel(make_order(status=OrderStatus.ACCEPTED))
    assert updated.status is OrderStatus.CANCEL_PENDING
    assert updated.status is not OrderStatus.CANCELLED


def test_expire_day_order(lifecycle: OrderLifecycle, make_order):
    updated = lifecycle.expire(
        make_order(status=OrderStatus.ACCEPTED, time_in_force=TimeInForce.DAY)
    )
    assert updated.status is OrderStatus.EXPIRED


def test_expire_gtc_order_rejected(lifecycle: OrderLifecycle, make_order):
    with pytest.raises(OrderValidationError):
        lifecycle.expire(
            make_order(
                status=OrderStatus.ACCEPTED,
                time_in_force=TimeInForce.GTC,
            )
        )


def test_expire_is_idempotent(lifecycle: OrderLifecycle, make_order):
    order = make_order(
        status=OrderStatus.EXPIRED, time_in_force=TimeInForce.DAY
    )
    assert lifecycle.expire(order) is order


def test_created_to_accepted_is_invalid(lifecycle: OrderLifecycle, make_order):
    with pytest.raises(InvalidOrderStateTransition):
        lifecycle.accept(make_order(status=OrderStatus.CREATED))


def test_filled_cannot_be_cancelled(lifecycle: OrderLifecycle, make_order):
    # Spec #28: terminal states never move again.
    with pytest.raises(InvalidOrderStateTransition):
        lifecycle.cancel(make_order(status=OrderStatus.FILLED))


def test_filled_cannot_be_submitted(lifecycle: OrderLifecycle, make_order):
    with pytest.raises(InvalidOrderStateTransition):
        lifecycle.submit(make_order(status=OrderStatus.FILLED))


def test_transition_preserves_lineage_and_created_at(
    lifecycle: OrderLifecycle, make_order
):
    created_at = datetime(2026, 8, 13, 9, 0, 0)
    updated_at = datetime(2026, 8, 13, 9, 31, 0)
    order = make_order(status=OrderStatus.SUBMITTED, created_at=created_at)

    updated = lifecycle.accept(order, at=updated_at)

    assert updated.created_at == created_at  # never rewritten (Spec #20)
    assert updated.updated_at == updated_at
    assert updated.intent_id == order.intent_id
    assert updated.authorization_id == order.authorization_id
    assert updated.certificate_id == order.certificate_id
    assert updated.decision_id == order.decision_id
    assert updated.strategy_id == order.strategy_id
    assert updated.signal_id == order.signal_id
    assert updated.correlation_id == order.correlation_id
