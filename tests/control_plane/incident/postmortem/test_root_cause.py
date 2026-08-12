"""Structured root cause model."""

from __future__ import annotations

from services.control_plane.incident.postmortem.root_cause import (
    RootCause,
    RootCauseCategory,
)


def test_root_cause_holds_category_and_summary():
    cause = RootCause(
        category=RootCauseCategory.INFRASTRUCTURE,
        summary="api gateway overloaded",
    )
    assert cause.category == RootCauseCategory.INFRASTRUCTURE
    assert cause.summary == "api gateway overloaded"


def test_root_cause_defaults():
    cause = RootCause(
        category=RootCauseCategory.UNKNOWN,
        summary="to be determined",
    )
    assert cause.technical_detail == ""
    assert cause.contributing_factors is None
    assert cause.confidence == 0.0


def test_root_cause_optional_detail():
    cause = RootCause(
        category=RootCauseCategory.DATA,
        summary="stale market data",
        technical_detail="feed reconnect stalled",
        contributing_factors=["no redundancy", "alert gap"],
        confidence=0.9,
    )
    assert cause.contributing_factors == ["no redundancy", "alert gap"]
    assert cause.confidence == 0.9
