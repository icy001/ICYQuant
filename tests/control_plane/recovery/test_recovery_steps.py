"""Unit tests: the eight recovery step executors."""

from __future__ import annotations

import pytest

from services.control_plane.recovery.recovery_context import (
    RecoveryContext,
    RecoveryScope,
)
from services.control_plane.recovery.recovery_step import StepType, make_step
from services.control_plane.recovery_steps.freeze_state import FreezeStateExecutor
from services.control_plane.recovery_steps.isolate_trading import IsolateTradingExecutor
from services.control_plane.recovery_steps.rebuild_ledger import RebuildLedgerExecutor
from services.control_plane.recovery_steps.rebuild_position import (
    RebuildPositionExecutor,
)
from services.control_plane.recovery_steps.reconcile_state import ReconcileStateExecutor
from services.control_plane.recovery_steps.replay_events import ReplayEventsExecutor
from services.control_plane.recovery_steps.resume_trading import ResumeTradingExecutor
from services.control_plane.recovery_steps.verify_integrity import VerifyIntegrityExecutor


def _context(**overrides) -> RecoveryContext:
    defaults = {
        "recovery_id": "REC-1",
        "incident_id": "INC-1",
        "scope": RecoveryScope.STRATEGY,
        "correlation_id": "CORR-1",
    }
    defaults.update(overrides)
    return RecoveryContext(**defaults)


class TestRegistry:
    def test_all_step_types_registered(self):
        from services.control_plane.recovery_steps import registered_step_types

        types = registered_step_types()
        assert StepType.ISOLATE_TRADING in types
        assert StepType.FREEZE_STATE in types
        assert StepType.REPLAY_EVENTS in types
        assert StepType.REBUILD_LEDGER in types
        assert StepType.REBUILD_POSITION in types
        assert StepType.RECONCILE_STATE in types
        assert StepType.VERIFY_INTEGRITY in types
        assert StepType.RESUME_TRADING in types
        assert len(types) == 8

    def test_get_executor(self):
        from services.control_plane.recovery_steps import get_step_executor

        executor = get_step_executor(StepType.ISOLATE_TRADING)
        assert isinstance(executor, IsolateTradingExecutor)


class TestIsolateTrading:
    def test_already_halted_is_isolated(self):
        step = make_step(StepType.ISOLATE_TRADING, trading_state="HALTED")
        outcome = IsolateTradingExecutor().execute(step, _context())
        assert outcome.success
        assert outcome.output["isolated"] is True
        assert outcome.actions == []

    def test_ready_trading_requests_isolation(self):
        step = make_step(StepType.ISOLATE_TRADING, trading_state="TRADING_READY")
        outcome = IsolateTradingExecutor().execute(step, _context())
        assert outcome.success
        assert outcome.output["isolated"] is False
        assert len(outcome.actions) == 1
        assert outcome.actions[0].action == "ISOLATE_TRADING"

    def test_injected_isolator_wins(self):
        step = make_step(StepType.ISOLATE_TRADING, trading_state="TRADING_READY")
        executor = IsolateTradingExecutor(isolator=lambda ctx: {"isolated": True})
        outcome = executor.execute(step, _context())
        assert outcome.output["isolated"] is True
        assert outcome.actions == []


class TestFreezeState:
    def test_freezes_with_snapshot_id(self):
        step = make_step(StepType.FREEZE_STATE, target="POSITION")
        outcome = FreezeStateExecutor().execute(step, _context())
        assert outcome.success
        assert outcome.output["frozen"] is True
        assert outcome.output["snapshot_id"] == "SNAP-REC-1"
        assert outcome.actions[0].action == "FREEZE_STATE"

    def test_injected_freezer_provides_snapshot(self):
        step = make_step(StepType.FREEZE_STATE)
        executor = FreezeStateExecutor(freezer=lambda ctx: {"snapshot_id": "SNAP-X"})
        outcome = executor.execute(step, _context())
        assert outcome.output["snapshot_id"] == "SNAP-X"


class TestReplayEvents:
    def test_contiguous_events_succeed(self):
        events = [{"seq": 1, "type": "TRADE"}, {"seq": 2, "type": "TRADE"}]
        step = make_step(StepType.REPLAY_EVENTS, event_cursor=0, events=events)
        outcome = ReplayEventsExecutor().execute(step, _context())
        assert outcome.success
        assert outcome.output["replayed_events"] == 2
        assert outcome.output["event_cursor"] == 2
        assert outcome.output["complete"] is True

    def test_event_gap_fails(self):
        events = [
            {"seq": 100, "type": "T"},
            {"seq": 101, "type": "T"},
            {"seq": 103, "type": "T"},
        ]
        step = make_step(StepType.REPLAY_EVENTS, event_cursor=99, events=events)
        outcome = ReplayEventsExecutor().execute(step, _context())
        assert not outcome.success
        assert outcome.error_code == "EVENT_GAP"
        assert "102" in outcome.error

    def test_event_count_mismatch_fails(self):
        events = [{"seq": 1}, {"seq": 2}]
        step = make_step(
            StepType.REPLAY_EVENTS, event_cursor=0, events=events, expected_events=3
        )
        outcome = ReplayEventsExecutor().execute(step, _context())
        assert not outcome.success
        assert outcome.error_code == "EVENT_COUNT_MISMATCH"

    def test_checksum_mismatch_fails(self):
        events = [{"seq": 1}]
        step = make_step(
            StepType.REPLAY_EVENTS,
            event_cursor=0,
            events=events,
            expected_checksum="deadbeef",
        )
        outcome = ReplayEventsExecutor().execute(step, _context())
        assert not outcome.success
        assert outcome.error_code == "CHECKSUM_MISMATCH"

    def test_event_store_injection(self):
        store = lambda cursor: [  # noqa: E731
            {"seq": cursor + 1, "type": "T"},
            {"seq": cursor + 2, "type": "T"},
        ]
        step = make_step(StepType.REPLAY_EVENTS, event_cursor=10)
        outcome = ReplayEventsExecutor(event_store=store).execute(step, _context())
        assert outcome.success
        assert outcome.output["event_cursor"] == 12
        assert outcome.output["replayed_events"] == 2


class TestRebuildLedger:
    def test_injected_builder(self):
        step = make_step(
            StepType.REBUILD_LEDGER,
            ledger_snapshot={"ledger_version": "L-1", "balance": 1000},
        )
        builder = lambda snapshot, events, adjustments: {  # noqa: E731
            "ledger_version": "L-2",
            "balance": 1500,
            "balance_verified": True,
        }
        outcome = RebuildLedgerExecutor(ledger_builder=builder).execute(
            step, _context()
        )
        assert outcome.success
        assert outcome.output["ledger_version"] == "L-2"
        assert outcome.output["balance"] == 1500
        assert outcome.output["balance_verified"] is True

    def test_no_builder_requests_rebuild(self):
        step = make_step(
            StepType.REBUILD_LEDGER,
            ledger_snapshot={"ledger_version": "L-1", "balance": 1000},
        )
        outcome = RebuildLedgerExecutor().execute(step, _context())
        assert outcome.success
        assert outcome.output["ledger_version"] == "L-1"
        assert outcome.actions[0].action == "REBUILD_LEDGER"


class TestRebuildPosition:
    def test_matches_snapshot(self):
        step = make_step(
            StepType.REBUILD_POSITION,
            position_snapshot={"quantity": 500, "average_price": 100.0},
        )
        builder = lambda ledger, events, adjustments: {  # noqa: E731
            "position_version": "P-2",
            "quantity": 500,
            "average_price": 100.0,
        }
        outcome = RebuildPositionExecutor(position_builder=builder).execute(
            step, _context()
        )
        assert outcome.success
        assert outcome.output["match"] is True
        assert outcome.output["position_version"] == "P-2"

    def test_divergence_from_snapshot(self):
        step = make_step(
            StepType.REBUILD_POSITION,
            position_snapshot={"quantity": 500, "average_price": 100.0},
        )
        builder = lambda ledger, events, adjustments: {  # noqa: E731
            "position_version": "P-2",
            "quantity": 400,
            "average_price": 100.0,
        }
        outcome = RebuildPositionExecutor(position_builder=builder).execute(
            step, _context()
        )
        assert outcome.success
        assert outcome.output["match"] is False


class TestReconcileState:
    def test_match_when_quantities_align(self):
        step = make_step(StepType.RECONCILE_STATE, ledger_quantity=100, position_quantity=100)
        outcome = ReconcileStateExecutor().execute(step, _context())
        assert outcome.success
        assert outcome.output["reconciliation"] == "MATCH"

    def test_mismatch_fails(self):
        step = make_step(StepType.RECONCILE_STATE, ledger_quantity=100, position_quantity=99)
        outcome = ReconcileStateExecutor().execute(step, _context())
        assert not outcome.success
        assert outcome.error_code == "RECONCILIATION_MISMATCH"
        assert outcome.output["ledger_vs_position"] == "MISMATCH"

    def test_reads_rebuild_outputs_from_context(self):
        context = _context()
        context.step_outputs["REBUILD_LEDGER"] = {"balance": 100}
        context.step_outputs["REBUILD_POSITION"] = {
            "reconstructed": {"quantity": 100}
        }
        outcome = ReconcileStateExecutor().execute(make_step(StepType.RECONCILE_STATE), context)
        assert outcome.success
        assert outcome.output["ledger_vs_position"] == "MATCH"

    def test_injected_comparator(self):
        step = make_step(StepType.RECONCILE_STATE)
        comparator = lambda ctx, s: {  # noqa: E731
            "ledger_vs_position": "MISMATCH",
            "event_vs_ledger": "MISMATCH",
        }
        outcome = ReconcileStateExecutor(comparator=comparator).execute(step, _context())
        assert not outcome.success


class TestVerifyIntegrity:
    def test_all_checks_pass(self):
        context = _context()
        context.step_outputs["REPLAY_EVENTS"] = {"complete": True, "event_cursor": 10}
        context.step_outputs["REBUILD_LEDGER"] = {"balance_verified": True}
        context.step_outputs["REBUILD_POSITION"] = {"match": True}
        context.step_outputs["RECONCILE_STATE"] = {"reconciliation": "MATCH"}
        outcome = VerifyIntegrityExecutor().execute(
            make_step(StepType.VERIFY_INTEGRITY), context
        )
        assert outcome.success
        assert outcome.output["verified"] is True
        assert outcome.output["checks"]["event_replay"] is True

    def test_unhealthy_risk_fails(self):
        from services.control_plane.domain.component_state import ComponentState

        step = make_step(StepType.VERIFY_INTEGRITY)
        outcome = VerifyIntegrityExecutor().execute(
            step, _context(risk_state=ComponentState.UNHEALTHY)
        )
        assert not outcome.success
        assert outcome.error_code == "INTEGRITY_VERIFICATION_FAILED"
        assert outcome.output["checks"]["risk_trusted"] is False

    def test_replay_missing_fails(self):
        step = make_step(StepType.VERIFY_INTEGRITY)
        outcome = VerifyIntegrityExecutor().execute(step, _context())
        # without any step outputs the event replay check must fail
        assert outcome.output["checks"]["event_replay"] is False
        assert not outcome.success

    def test_injected_verifier(self):
        step = make_step(StepType.VERIFY_INTEGRITY)
        verifier = lambda ctx, s: {"verified": True, "checks": {"custom": True}}  # noqa: E731
        outcome = VerifyIntegrityExecutor(verifier=verifier).execute(step, _context())
        assert outcome.success
        assert outcome.output["verified"] is True


class TestResumeTrading:
    def test_ramp_up_level(self):
        step = make_step(StepType.RESUME_TRADING, ramp_up_level="LEVEL_2")
        outcome = ResumeTradingExecutor().execute(step, _context())
        assert outcome.success
        assert outcome.output["ramp_up_level"] == "LEVEL_2"
        assert outcome.actions[0].action == "RESUME_TRADING"
        assert outcome.actions[0].detail == "LEVEL_2"

    def test_injected_gate(self):
        step = make_step(StepType.RESUME_TRADING, ramp_up_level="LEVEL_1")
        gate = lambda ctx, level: {"resumed": False}  # noqa: E731
        outcome = ResumeTradingExecutor(gate=gate).execute(step, _context())
        assert outcome.output["resumed"] is False
