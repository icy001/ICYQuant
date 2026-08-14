"""Replay protection tests (Commit 29 Part 1.4 §28-31, §49).

Idempotency handles *the same request submitted twice*; replay protection
handles *an old request pulled out and re-executed* (§30).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.control_plane import ReplayPolicy, ReplayProtector


def _now() -> datetime:
    return datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)


class TestReplayWindow:
    def test_fresh_request_is_allowed(self):
        protector = ReplayProtector(ReplayPolicy(max_age_seconds=300))
        decision = protector.check(_now() - timedelta(seconds=10), now=_now())
        assert decision.allowed is True

    def test_expired_request_is_rejected(self):
        """§49: a request older than the window returns REPLAY_REJECTED."""
        protector = ReplayProtector(ReplayPolicy(max_age_seconds=300))
        decision = protector.check(_now() - timedelta(seconds=301), now=_now())
        assert decision.allowed is False
        assert decision.error_code == "REPLAY_REJECTED"

    def test_age_exactly_at_window_boundary_is_allowed(self):
        protector = ReplayProtector(ReplayPolicy(max_age_seconds=300))
        decision = protector.check(_now() - timedelta(seconds=300), now=_now())
        assert decision.allowed is True

    def test_hour_old_command_is_rejected_with_short_window(self):
        protector = ReplayProtector(ReplayPolicy(max_age_seconds=3600))
        decision = protector.check(_now() - timedelta(hours=2), now=_now())
        assert decision.allowed is False

    def test_default_policy_uses_five_minute_window(self):
        protector = ReplayProtector()
        assert protector.policy.max_age_seconds == 300


class TestCompletedCommandReplay:
    def test_completed_replay_allowed_by_default(self):
        """§31: allow_completed_replay defaults to True — historical result only."""
        protector = ReplayProtector(ReplayPolicy(max_age_seconds=300))
        decision = protector.check_command_state("SUCCEEDED")
        assert decision.allowed is True

    def test_completed_replay_rejected_when_disabled(self):
        protector = ReplayProtector(
            ReplayPolicy(max_age_seconds=300, allow_completed_replay=False)
        )
        for state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            decision = protector.check_command_state(state)
            assert decision.allowed is False
            assert decision.error_code == "REPLAY_REJECTED"

    def test_running_command_replay_is_always_allowed(self):
        protector = ReplayProtector(
            ReplayPolicy(max_age_seconds=300, allow_completed_replay=False)
        )
        for state in ("NEW_COMMAND", "WAITING_APPROVAL", "EXECUTING"):
            assert protector.check_command_state(state).allowed is True

    def test_check_command_uses_command_state(self):
        from types import SimpleNamespace

        protector = ReplayProtector(
            ReplayPolicy(max_age_seconds=300, allow_completed_replay=False)
        )
        completed = SimpleNamespace(state="SUCCEEDED")
        assert protector.check_command(completed).allowed is False


class TestEndToEndReplay:
    def test_expired_request_is_rejected_before_execution(self, make_command, make_request):
        """§49: REPLAY_REJECTED reaches the caller and the executor never runs."""
        from unittest.mock import MagicMock

        from services.control_plane import (
            ControlResult,
            DuplicateDetector,
            IdempotencyService,
            InMemoryIdempotencyStore,
            ReplayProtector,
        )

        detector = DuplicateDetector(InMemoryIdempotencyStore())
        executor = MagicMock(
            return_value=ControlResult(command_id="CMD-001", state="SUCCEEDED")
        )
        service = IdempotencyService(
            detector=detector,
            executor=executor,
            replay=ReplayProtector(ReplayPolicy(max_age_seconds=300)),
        )
        request = make_request(
            command=make_command(),
            submitted_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        result = service.submit(request)
        assert result.error_code == "REPLAY_REJECTED"
        executor.assert_not_called()
