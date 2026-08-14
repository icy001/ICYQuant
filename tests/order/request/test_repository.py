"""Tests for the OrderRequestRepository boundary (Commit 32 Part 1.5).

The repository only saves, reads and updates state — it never validates,
normalizes or makes trading decisions.  Snapshots carry the full authorization
lineage so a request can be recovered and audited independently.
"""

import pytest
from dataclasses import FrozenInstanceError

from services.order.request.exceptions import OrderRequestPersistenceError
from services.order.request.model import OrderRequest
from services.order.request.repository import (
    InMemoryOrderRequestRepository,
    OrderRequestSnapshot,
)
from services.order.request.state import OrderRequestState


def make_request(**overrides) -> OrderRequest:
    defaults = dict(
        order_request_id="OR-001",
        intent_id="INT-001",
        authorization_id="AUTH-001",
        certificate_id="CERT-001",
        decision_id="RISK-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
        symbol="NVDA",
        side="BUY",
        quantity=100.0,
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1000.0,
        idempotency_key="STRAT-001:SESSION-001:INT-001",
    )
    defaults.update(overrides)
    return OrderRequest(**defaults)


@pytest.fixture
def repository() -> InMemoryOrderRequestRepository:
    return InMemoryOrderRequestRepository()


def test_save_and_get_roundtrip(repository):
    repository.save(make_request(), state=OrderRequestState.CREATED)
    snapshot = repository.get("OR-001")
    assert snapshot is not None
    assert snapshot.order_request_id == "OR-001"
    assert snapshot.state == OrderRequestState.CREATED
    assert snapshot.symbol == "NVDA"
    assert snapshot.correlation_id == "CORR-001"


def test_snapshot_includes_full_authorization_lineage(repository):
    repository.save(make_request(), state=OrderRequestState.CREATED)
    snapshot = repository.get("OR-001")
    assert snapshot.intent_id == "INT-001"
    assert snapshot.authorization_id == "AUTH-001"
    assert snapshot.certificate_id == "CERT-001"
    assert snapshot.decision_id == "RISK-001"
    assert snapshot.strategy_id == "STRAT-001"
    assert snapshot.session_id == "SESSION-001"
    assert snapshot.signal_id == "SIG-001"


def test_update_state_persists_new_state(repository):
    repository.save(make_request())
    repository.update_state("OR-001", OrderRequestState.SUBMITTED)
    assert repository.get("OR-001").state == OrderRequestState.SUBMITTED


def test_update_state_missing_raises_key_error(repository):
    with pytest.raises(KeyError):
        repository.update_state("OR-MISSING", OrderRequestState.SUBMITTED)


def test_get_missing_returns_none(repository):
    assert repository.get("OR-MISSING") is None


def test_save_is_idempotent_by_id(repository):
    repository.save(make_request(), state=OrderRequestState.CREATED)
    repository.save(make_request(), state=OrderRequestState.CREATED)
    assert len(repository) == 1
    assert repository.get("OR-001").state == OrderRequestState.CREATED


def test_find_by_idempotency_key(repository):
    repository.save(make_request())
    found = repository.find_by_idempotency_key("STRAT-001:SESSION-001:INT-001")
    assert found is not None
    assert found.order_request_id == "OR-001"
    assert repository.find_by_idempotency_key("UNKNOWN:KEY") is None


def test_fail_on_save_raises_persistence_error(repository):
    repository.fail_on_save = True
    with pytest.raises(OrderRequestPersistenceError):
        repository.save(make_request())


def test_fail_on_update_raises_persistence_error(repository):
    repository.save(make_request())
    repository.fail_on_update = True
    with pytest.raises(OrderRequestPersistenceError):
        repository.update_state("OR-001", OrderRequestState.SUBMITTED)


def test_snapshot_from_request_to_request_roundtrip():
    request = make_request()
    snapshot = OrderRequestSnapshot.from_request(
        request,
        state=OrderRequestState.VALIDATED,
    )
    assert snapshot.state == OrderRequestState.VALIDATED
    assert snapshot.to_request() == request


def test_snapshot_with_state_keeps_data_unchanged():
    request = make_request()
    snapshot = OrderRequestSnapshot.from_request(
        request,
        state=OrderRequestState.CREATED,
    )
    advanced = snapshot.with_state(OrderRequestState.SUBMITTED)
    assert advanced.state == OrderRequestState.SUBMITTED
    assert advanced.to_request() == request


def test_snapshot_is_frozen():
    snapshot = OrderRequestSnapshot.from_request(
        make_request(),
        state=OrderRequestState.CREATED,
    )
    with pytest.raises(FrozenInstanceError):
        snapshot.quantity = 500.0
