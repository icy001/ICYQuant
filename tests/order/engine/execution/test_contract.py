"""Tests for the execution gateway contract (Commit 33 Part 1.3 #9/#29).

The :class:`ExecutionGateway` protocol is the only external execution entry
point.  These tests pin the structural contract so paper / live / backtest
adapters can be swapped behind the same boundary.
"""

from __future__ import annotations

from services.order.engine.execution.contract import ExecutionGateway
from services.order.engine.execution.gateway import FakeExecutionGateway


def test_fake_gateway_satisfies_the_protocol():
    # The protocol is runtime-checkable: conformance is enforced structurally.
    assert isinstance(FakeExecutionGateway(), ExecutionGateway)


def test_protocol_exposes_submit_cancel_query():
    # A conforming gateway must answer submit / cancel / query.
    assert hasattr(ExecutionGateway, "submit")
    assert hasattr(ExecutionGateway, "cancel")
    assert hasattr(ExecutionGateway, "query")
