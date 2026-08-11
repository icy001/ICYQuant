"""
Test DecisionSnapshot, DecisionRecord, DecisionTrace — core audit record types.
"""

import pytest

from services.governance.decision_snapshot import DecisionSnapshot
from services.governance.decision_record import DecisionRecord, DecisionRecordStatus
from services.governance.decision_trace import DecisionTrace, TraceStep, TraceStepRecord
from services.governance.decision_reason import DecisionReason, ReasonType
from services.governance.decision_evidence import DecisionEvidence
from services.governance.audit_hash import AuditHash


class TestDecisionSnapshot:
    """Test decision snapshot creation and verification."""

    def test_create_snapshot(self):
        snap = DecisionSnapshot(
            snapshot_id="SNAP-001",
            decision_id="DEC-001",
            market_snapshot={"NVDA": 182.40},
            risk_snapshot={"VaR": 1.8e6, "survival": 76},
            policy_id="POL-CAP-001",
            policy_version="v4",
            authority_id="AUTH-001",
            decision_type="CAPITAL_ALLOCATION",
            instrument="NVDA",
            side="BUY",
            amount=25_000_000,
            correlation_id="CORR-001",
        )
        snap.compute_component_hashes()
        snap.compute_hash()
        assert snap.snapshot_hash.startswith("sha256:")

    def test_verify_snapshot(self):
        snap = DecisionSnapshot(
            snapshot_id="SNAP-002",
            decision_id="DEC-002",
            market_snapshot={"AAPL": 225.00},
            risk_snapshot={"stress": 78},
            policy_id="POL-001",
            policy_version="v1",
            policy_hash="",
            correlation_id="CORR-002",
        )
        snap.compute_hash()
        result = snap.verify()
        assert result["valid"] is True

    def test_verify_tampered_snapshot(self):
        snap = DecisionSnapshot(
            snapshot_id="SNAP-003",
            decision_id="DEC-003",
            market_snapshot={"GOOGL": 190.00},
            risk_snapshot={"VaR": 500000},
            policy_id="POL-001",
            policy_version="v1",
            correlation_id="CORR-003",
        )
        snap.compute_hash()
        # Tamper with the snapshot
        snap.amount = 999_999_999
        result = snap.verify()
        assert result["valid"] is False

    def test_to_from_dict(self):
        snap = DecisionSnapshot(
            snapshot_id="SNAP-004",
            decision_id="DEC-004",
            market_snapshot={"MSFT": 420.00},
            risk_snapshot={"leverage": 2.5},
            policy_id="POL-CAP-001",
            policy_version="v3",
            decision_type="RISK_REDUCTION",
            amount=10_000_000,
            correlation_id="CORR-004",
        )
        d = snap.to_dict()
        restored = DecisionSnapshot.from_dict(d)
        assert restored.snapshot_id == "SNAP-004"
        assert restored.decision_id == "DEC-004"


class TestDecisionRecord:
    """Test DecisionRecord creation and lifecycle."""

    def test_create_record(self):
        record = DecisionRecord(
            record_id="REC-001",
            decision_id="DEC-001",
            decision_type="CAPITAL_ALLOCATION",
            instrument="NVDA",
            side="BUY",
            amount=25_000_000,
            correlation_id="CORR-001",
        )
        assert record.record_id == "REC-001"
        assert record.status == DecisionRecordStatus.CREATED

    def test_status_lifecycle(self):
        record = DecisionRecord(
            record_id="REC-002",
            decision_id="DEC-002",
            correlation_id="CORR-002",
        )
        assert record.is_terminal() is False

        record.set_status(DecisionRecordStatus.EVALUATING)
        assert record.status == DecisionRecordStatus.EVALUATING

        record.set_status(DecisionRecordStatus.APPROVED)
        assert record.status == DecisionRecordStatus.APPROVED

        record.set_status(DecisionRecordStatus.EXECUTED)
        assert record.status == DecisionRecordStatus.EXECUTED
        assert record.is_terminal() is True

    def test_compute_hash(self):
        record = DecisionRecord(
            record_id="REC-003",
            decision_id="DEC-003",
            decision_type="CAPITAL_ALLOCATION",
            instrument="AAPL",
            side="BUY",
            amount=10_000_000,
            correlation_id="CORR-003",
        )
        h = record.compute_hash()
        assert h.startswith("sha256:")

    def test_to_from_dict(self):
        record = DecisionRecord(
            record_id="REC-004",
            decision_id="DEC-004",
            decision_type="RISK_REDUCTION",
            instrument="TSLA",
            side="SELL",
            amount=5_000_000,
            correlation_id="CORR-004",
        )
        d = record.to_dict()
        restored = DecisionRecord.from_dict(d)
        assert restored.decision_id == "DEC-004"
        assert restored.decision_type == "RISK_REDUCTION"
        assert restored.amount == 5_000_000


class TestDecisionTrace:
    """Test decision trace recording."""

    def test_add_steps(self):
        trace = DecisionTrace(
            trace_id="TRACE-001",
            correlation_id="CORR-001",
            decision_id="DEC-001",
        )
        trace.add_step(TraceStep.DECISION_CREATED)
        trace.complete_step("OK", "Decision created")

        trace.add_step(TraceStep.POLICY_CHECK, entity_id="POL-001", entity_type="POLICY")
        trace.complete_step("OK")

        assert len(trace.steps) == 2
        assert trace.final_status == "PENDING"

    def test_fail_step(self):
        trace = DecisionTrace(trace_id="TRACE-002", correlation_id="CORR-002", decision_id="DEC-002")
        trace.add_step(TraceStep.DECISION_CREATED)
        trace.complete_step()

        trace.add_step(TraceStep.POLICY_CHECK)
        trace.fail_step("Allocation exceeds limit")

        assert trace.final_status == "BLOCKED"
        assert len(trace.get_failed_steps()) == 1

    def test_complete_trace(self):
        trace = DecisionTrace(trace_id="TRACE-003", correlation_id="CORR-003", decision_id="DEC-003")
        trace.add_step(TraceStep.DECISION_CREATED)
        trace.complete_step()
        trace.complete("COMPLETED")

        assert trace.final_status == "COMPLETED"
        assert trace.total_duration_ms > 0


class TestDecisionReason:
    """Test decision reasons."""

    def test_create_reason(self):
        reason = DecisionReason(
            reason_id="RSN-001",
            reason_type=ReasonType.SIGNAL,
            reason_text="Momentum breakout confirmed",
            confidence=0.87,
            source="momentum-v7",
        )
        assert reason.reason_type == ReasonType.SIGNAL
        assert reason.confidence == 0.87
        assert reason.source == "momentum-v7"


class TestDecisionEvidence:
    """Test decision evidence."""

    def test_create_evidence(self):
        ev = DecisionEvidence(evidence_id="EVD-001", decision_id="DEC-001")
        ev.add_factor("Momentum", 0.92, unit="z-score")
        ev.add_market("Volume", "+34%", description="Above average volume")
        ev.add_risk("VaR", 1_800_000, unit="USD")

        assert len(ev.all_items) == 3
        assert len(ev.factor_evidence) == 1
        assert len(ev.market_evidence) == 1
        assert len(ev.risk_evidence) == 1

    def test_get_evidence_by_key(self):
        ev = DecisionEvidence(evidence_id="EVD-002")
        ev.add_factor("Momentum", 0.92)

        item = ev.get("Momentum")
        assert item is not None
        assert item.value == 0.92

        missing = ev.get("Nonexistent")
        assert missing is None
