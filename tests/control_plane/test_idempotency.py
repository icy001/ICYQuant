"""Idempotency key model tests (Commit 29 Part 1.4 §3-5, §42).

The idempotency key answers *"this is the same business operation"*, unlike
the request id which only identifies *"this one message"* (§5).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.control_plane import IdempotencyKey


def _now() -> datetime:
    return datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)


class TestIdempotencyKey:
    def test_key_carries_value_created_at_principal(self):
        key = IdempotencyKey(
            value="IDEMP-20260813-000001",
            created_at=_now(),
            principal_id="operator-001",
        )
        assert key.value == "IDEMP-20260813-000001"
        assert key.principal_id == "operator-001"
        assert key.created_at == _now()

    def test_identity_combines_value_and_principal(self):
        """value + principal_id jointly form the unique request identity (§4)."""
        a = IdempotencyKey("IDEMP-001", _now(), "ops-001")
        b = IdempotencyKey("IDEMP-001", _now(), "ops-001")
        c = IdempotencyKey("IDEMP-001", _now(), "ops-002")
        assert a.identity() == ("IDEMP-001", "ops-001")
        assert a.identity() == b.identity()
        assert a.identity() != c.identity()

    def test_key_is_frozen(self):
        key = IdempotencyKey("IDEMP-001", _now(), "ops-001")
        with pytest.raises(AttributeError):
            key.value = "IDEMP-002"  # type: ignore[misc]

    def test_not_expired_within_ttl(self):
        key = IdempotencyKey("IDEMP-001", _now(), "ops-001")
        later = _now() + timedelta(seconds=299)
        assert key.is_expired(ttl_seconds=300, now=later) is False

    def test_expired_after_ttl(self):
        key = IdempotencyKey("IDEMP-001", _now(), "ops-001")
        later = _now() + timedelta(seconds=301)
        assert key.is_expired(ttl_seconds=300, now=later) is True

    def test_request_id_and_idempotency_key_are_different_concepts(self, make_request):
        """REQ-001/REQ-002/REQ-003 may all belong to IDEMP-001 (§5)."""
        request_a = make_request(request_id="REQ-001", idempotency_key="IDEMP-001")
        request_b = make_request(request_id="REQ-002", idempotency_key="IDEMP-001")
        request_c = make_request(request_id="REQ-003", idempotency_key="IDEMP-001")
        assert request_a.idempotency_key == request_b.idempotency_key
        assert request_b.idempotency_key == request_c.idempotency_key
        assert request_a.request_id != request_b.request_id
        assert request_b.request_id != request_c.request_id
