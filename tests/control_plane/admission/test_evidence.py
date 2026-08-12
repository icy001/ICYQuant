"""Tests for AdmissionEvidence (spec section 13)."""
from __future__ import annotations

from uuid import uuid4

from services.control_plane.admission.evidence import AdmissionEvidence


def test_evidence_records_full_trace():
    request_id = uuid4()
    evidence = AdmissionEvidence(
        request_id=request_id,
        risk_decision="APPROVED",
        control_decision="REDUCE_ONLY",
        final_decision="REJECTED",
        reason="CONTROL_REDUCE_ONLY",
    )

    assert evidence.evidence_id is not None
    assert evidence.request_id == request_id
    assert evidence.risk_decision == "APPROVED"
    assert evidence.control_decision == "REDUCE_ONLY"
    assert evidence.final_decision == "REJECTED"
    assert evidence.reason == "CONTROL_REDUCE_ONLY"
    assert evidence.created_at.tzinfo is not None


def test_evidence_is_frozen():
    import pytest
    from dataclasses import FrozenInstanceError

    evidence = AdmissionEvidence(
        request_id=uuid4(),
        risk_decision="APPROVED",
        control_decision="ALLOW",
        final_decision="ACCEPTED",
        reason="CONTROL_ALLOWED",
    )

    with pytest.raises(FrozenInstanceError):
        evidence.final_decision = "REJECTED"  # type: ignore[misc]


def test_evidence_ids_are_unique():
    a = AdmissionEvidence(
        request_id=uuid4(),
        risk_decision="APPROVED",
        control_decision="ALLOW",
        final_decision="ACCEPTED",
        reason="CONTROL_ALLOWED",
    )
    b = AdmissionEvidence(
        request_id=uuid4(),
        risk_decision="APPROVED",
        control_decision="ALLOW",
        final_decision="ACCEPTED",
        reason="CONTROL_ALLOWED",
    )

    assert a.evidence_id != b.evidence_id
