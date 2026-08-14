"""Execution claim, lease and fencing token tests (Commit 29 Part 1.4 §20-27, §51-52).

A claim is ownership proof, not a permanent lock: the worker heartbeats to
keep the lease alive, and a recovery worker taking over gets a *higher*
fencing token so a zombie worker can never write (§22, §24-25).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.control_plane import ControlExecutor, ExecutionClaimStore


def _now() -> datetime:
    return datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)


class TestClaimAcquisition:
    def test_acquire_succeeds_for_first_worker(self):
        claims = ExecutionClaimStore(lease_seconds=30)
        claim = claims.acquire("CMD-001", "worker-a", now=_now())
        assert claim is not None
        assert claim.command_id == "CMD-001"
        assert claim.worker_id == "worker-a"
        assert claim.fencing_token == 1

    def test_only_one_worker_can_claim(self):
        """§51: a second worker cannot claim while the first lease is live."""
        claims = ExecutionClaimStore(lease_seconds=30)
        claim_a = claims.acquire("CMD-001", "worker-a", now=_now())
        claim_b = claims.acquire("CMD-001", "worker-b", now=_now())
        assert claim_a is not None
        assert claim_b is None

    def test_claim_result_reports_held(self):
        claims = ExecutionClaimStore(lease_seconds=30)
        claims.acquire("CMD-001", "worker-a", now=_now())
        result = claims.acquire_with_result("CMD-001", "worker-b", now=_now())
        assert result.acquired is False
        assert result.error_code == "CLAIM_ALREADY_HELD"

    def test_lease_expiry_allows_takeover_with_higher_token(self):
        """§22-24: an expired lease can be taken over by a recovery worker."""
        claims = ExecutionClaimStore(lease_seconds=30)
        old_claim = claims.acquire("CMD-001", "worker-a", now=_now())
        assert old_claim.fencing_token == 1
        new_claim = claims.acquire(
            "CMD-001", "worker-b", now=_now() + timedelta(seconds=31)
        )
        assert new_claim is not None
        assert new_claim.worker_id == "worker-b"
        assert new_claim.fencing_token == 2

    def test_heartbeat_extends_lease(self):
        claims = ExecutionClaimStore(lease_seconds=30)
        claims.acquire("CMD-001", "worker-a", now=_now())
        renewed = claims.heartbeat(
            "CMD-001", "worker-a", now=_now() + timedelta(seconds=20)
        )
        assert renewed is True
        # Without the heartbeat the claim would have expired at +30s.
        take_over = claims.acquire(
            "CMD-001", "worker-b", now=_now() + timedelta(seconds=35)
        )
        assert take_over is None

    def test_heartbeat_by_other_worker_fails(self):
        claims = ExecutionClaimStore(lease_seconds=30)
        claims.acquire("CMD-001", "worker-a", now=_now())
        assert claims.heartbeat("CMD-001", "worker-b", now=_now()) is False

    def test_release_frees_the_claim(self):
        claims = ExecutionClaimStore(lease_seconds=30)
        claims.acquire("CMD-001", "worker-a", now=_now())
        assert claims.release("CMD-001", "worker-a") is True
        assert claims.release("CMD-001", "worker-a") is False
        next_claim = claims.acquire("CMD-001", "worker-b", now=_now())
        assert next_claim is not None

    def test_fencing_token_monotonically_increases(self):
        claims = ExecutionClaimStore(lease_seconds=30)
        first = claims.acquire("CMD-001", "worker-a", now=_now())
        assert first.fencing_token == 1
        claims.release("CMD-001", "worker-a")
        second = claims.acquire("CMD-001", "worker-b", now=_now())
        assert second.fencing_token == 2


class TestExecutorFencingGuard:
    def test_current_claim_can_execute(self):
        """§52: the current, unexpired fencing token may execute."""
        claims = ExecutionClaimStore(lease_seconds=30)
        executor = ControlExecutor(claim_store=claims)
        claim = claims.acquire("CMD-001", "worker-a", now=_now())
        assert executor.can_execute(claim, now=_now())

    def test_old_worker_cannot_execute(self):
        """§52: a zombie worker with a stale fencing token is refused."""
        claims = ExecutionClaimStore(lease_seconds=30)
        executor = ControlExecutor(claim_store=claims)
        old_claim = claims.acquire("CMD-001", "worker-a", now=_now())
        new_claim = claims.acquire(
            "CMD-001", "worker-b", now=_now() + timedelta(seconds=31)
        )
        assert new_claim is not None
        assert old_claim.fencing_token < new_claim.fencing_token
        assert executor.can_execute(new_claim, now=_now() + timedelta(seconds=31))
        assert not executor.can_execute(old_claim, now=_now() + timedelta(seconds=31))

    def test_expired_claim_cannot_execute(self):
        claims = ExecutionClaimStore(lease_seconds=30)
        executor = ControlExecutor(claim_store=claims)
        claim = claims.acquire("CMD-001", "worker-a", now=_now())
        assert executor.can_execute(claim, now=_now())
        assert not executor.can_execute(claim, now=_now() + timedelta(seconds=31))

    def test_none_claim_cannot_execute(self):
        executor = ControlExecutor()
        assert not executor.can_execute(None)

    def test_executor_without_claim_store_accepts_current_token(self):
        """Without a claim store the guard falls back to lease validity only."""
        claims = ExecutionClaimStore(lease_seconds=30)
        executor = ControlExecutor()
        claim = claims.acquire("CMD-001", "worker-a", now=_now())
        assert executor.can_execute(claim, now=_now())
