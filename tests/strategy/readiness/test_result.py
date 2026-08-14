"""Tests for the readiness result model."""

from services.strategy.readiness.result import ReadinessResult


def make_result(**overrides) -> ReadinessResult:
    fields = {
        "strategy_id": "STRAT-001",
        "state": "READY",
        "ready": True,
        "reasons": (),
        "checked_at": 1000.0,
    }
    fields.update(overrides)
    return ReadinessResult(**fields)


def test_readiness_result_fields() -> None:
    result = make_result(
        state="BLOCKED",
        ready=False,
        reasons=("risk",),
        evaluation_id="READINESS-20260813-000001",
        ttl=5.0,
    )
    assert result.strategy_id == "STRAT-001"
    assert result.state == "BLOCKED"
    assert result.ready is False
    assert result.reasons == ("risk",)
    assert result.checked_at == 1000.0
    assert result.evaluation_id == "READINESS-20260813-000001"
    assert result.ttl == 5.0


def test_readiness_result_is_frozen() -> None:
    result = make_result()
    try:
        result.ready = False
    except Exception:
        return
    raise AssertionError("ReadinessResult must be frozen")


def test_readiness_result_never_expires_without_ttl() -> None:
    result = make_result()
    assert result.expired(now=1000.0 + 3600.0) is False


def test_readiness_result_expires_after_ttl() -> None:
    result = make_result(checked_at=1000.0, ttl=5.0)
    assert result.expired(now=1004.0) is False
    assert result.expired(now=1005.0 + 0.001) is True


def test_readiness_result_expired_is_exclusive() -> None:
    result = make_result(checked_at=1000.0, ttl=5.0)
    # Exactly at the TTL boundary the result is still valid.
    assert result.expired(now=1005.0) is False
