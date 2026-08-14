"""Tests for the order engine commands (Commit 33 Part 1.2)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from services.order.engine.command import (
    AcceptOrderCommand,
    CancelOrderCommand,
    CreateOrderCommand,
    ExpireOrderCommand,
    RejectOrderCommand,
    SubmitOrderCommand,
)

TIMESTAMP = datetime(2026, 8, 13, 9, 30, 0)


def test_create_order_command_fields():
    command = CreateOrderCommand(
        order_request_id="OR-20260813-000001",
        client_order_id="ICY-ORD-20260813-000001",
        correlation_id="CORR-001",
        causation_id=None,
        timestamp=TIMESTAMP,
    )
    assert command.order_request_id == "OR-20260813-000001"
    assert command.client_order_id == "ICY-ORD-20260813-000001"
    assert command.correlation_id == "CORR-001"
    assert command.causation_id is None
    assert command.timestamp == TIMESTAMP


def test_create_command_carries_no_trading_parameters():
    # Spec #3: symbol / side / quantity / price live in the order request only.
    command = CreateOrderCommand(
        order_request_id="OR-20260813-000001",
        client_order_id="ICY-ORD-20260813-000001",
        correlation_id="CORR-001",
        causation_id=None,
        timestamp=TIMESTAMP,
    )
    assert not hasattr(command, "symbol")
    assert not hasattr(command, "side")
    assert not hasattr(command, "quantity")
    assert not hasattr(command, "limit_price")


def test_submit_accept_cancel_expire_share_command_shape():
    for command_cls in (
        SubmitOrderCommand,
        AcceptOrderCommand,
        CancelOrderCommand,
        ExpireOrderCommand,
    ):
        command = command_cls(
            order_id="ORD-001",
            correlation_id="CORR-001",
            causation_id="CAUSE-001",
            timestamp=TIMESTAMP,
        )
        assert command.order_id == "ORD-001"
        assert command.correlation_id == "CORR-001"
        assert command.causation_id == "CAUSE-001"


def test_reject_command_records_reason():
    command = RejectOrderCommand(
        order_id="ORD-001",
        reason="BROKER_REJECTED",
        correlation_id="CORR-001",
        causation_id=None,
        timestamp=TIMESTAMP,
    )
    assert command.order_id == "ORD-001"
    assert command.reason == "BROKER_REJECTED"


@pytest.mark.parametrize(
    "command_cls",
    [
        CreateOrderCommand,
        SubmitOrderCommand,
        AcceptOrderCommand,
        RejectOrderCommand,
        CancelOrderCommand,
        ExpireOrderCommand,
    ],
)
def test_all_commands_are_frozen(command_cls):
    if command_cls is CreateOrderCommand:
        command = command_cls(
            order_request_id="OR-001",
            client_order_id="ICY-ORD-001",
            correlation_id="CORR-001",
            causation_id=None,
            timestamp=TIMESTAMP,
        )
    elif command_cls is RejectOrderCommand:
        command = command_cls(
            order_id="ORD-001",
            reason="RISK_REJECTED",
            correlation_id="CORR-001",
            causation_id=None,
            timestamp=TIMESTAMP,
        )
    else:
        command = command_cls(
            order_id="ORD-001",
            correlation_id="CORR-001",
            causation_id=None,
            timestamp=TIMESTAMP,
        )
    with pytest.raises(FrozenInstanceError):
        command.timestamp = TIMESTAMP  # type: ignore[misc]
