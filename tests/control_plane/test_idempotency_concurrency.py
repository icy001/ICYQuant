"""Concurrent submission tests (Commit 29 Part 1.4 §40, §46).

Atomic Check+Create is the core requirement: 10 concurrent submissions of
the same idempotency key must produce exactly one command (§46). Without an
atomic claim two workers could both see *Not Found* and create CMD-001 and
CMD-002 (§20).
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from services.control_plane import (
    ControlResult,
    DuplicateDetector,
    IdempotencyRecord,
    IdempotencyService,
    InMemoryIdempotencyStore,
)


class CountingExecutor:
    """Thread-safe executor that counts how many times it actually ran."""

    def __init__(self) -> None:
        self.count = 0
        self._lock = threading.Lock()

    def __call__(self, request) -> ControlResult:
        with self._lock:
            self.count += 1
        return ControlResult(
            command_id=request.command.command_id,
            state="SUCCEEDED",
            success=True,
        )


def _run_concurrently(fn, workers: int = 10) -> list:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fn) for _ in range(workers)]
        return [future.result() for future in futures]


class TestConcurrentSubmission:
    def test_concurrent_requests_create_one_command(self, make_command, make_request):
        """§46: 10 requests -> exactly 1 command, exactly 1 execution."""
        executor = CountingExecutor()
        service = IdempotencyService(
            detector=DuplicateDetector(InMemoryIdempotencyStore()),
            executor=executor,
        )
        request = make_request(command=make_command())

        results = _run_concurrently(lambda: service.submit(request), workers=10)

        command_ids = {result.command_id for result in results}
        assert len(command_ids) == 1
        assert executor.count == 1
        assert sum(r.duplicate for r in results) == 9

    def test_concurrent_atomic_create_never_overwrites(self, make_command, make_request):
        """§40: Check+Create is atomic — the store never loses or replaces a record."""
        store = InMemoryIdempotencyStore()
        detector = DuplicateDetector(store)
        executor = CountingExecutor()
        service = IdempotencyService(detector=detector, executor=executor)
        request = make_request(command=make_command())

        _run_concurrently(lambda: service.submit(request), workers=10)

        record = store.get("IDEMP-001")
        assert record is not None
        assert record.command_id == "CMD-001"

    def test_concurrent_conflicting_keys_are_rejected(self, make_command, make_request):
        """Two different commands racing on the same key still conflict once."""
        service = IdempotencyService(
            detector=DuplicateDetector(InMemoryIdempotencyStore()),
            executor=CountingExecutor(),
        )
        pause = make_request(command=make_command(action="pause"))
        kill = make_request(command=make_command(action="kill"))

        results = _run_concurrently(
            lambda: service.submit(pause), workers=5
        ) + _run_concurrently(lambda: service.submit(kill), workers=5)

        conflicts = [r for r in results if r.error_code == "IDEMPOTENCY_CONFLICT"]
        assert len(conflicts) >= 5
        duplicates = [r for r in results if r.duplicate]
        assert len(duplicates) >= 4

    def test_concurrent_different_keys_are_independent(self, make_command, make_request):
        executor = CountingExecutor()
        service = IdempotencyService(
            detector=DuplicateDetector(InMemoryIdempotencyStore()),
            executor=executor,
        )
        request_a = make_request(command=make_command(), idempotency_key="IDEMP-A")
        request_b = make_request(command=make_command(), idempotency_key="IDEMP-B")

        results = _run_concurrently(
            lambda: service.submit(request_a), workers=5
        ) + _run_concurrently(lambda: service.submit(request_b), workers=5)

        assert {r.command_id for r in results} == {"CMD-001"}
        assert executor.count == 2
        assert sum(r.duplicate for r in results) == 8


class TestStoreAtomicity:
    def test_create_is_atomic_under_contention(self):
        store = InMemoryIdempotencyStore()

        def submit(i: int) -> IdempotencyRecord:
            record = IdempotencyRecord(
                idempotency_key="IDEMP-001",
                principal_id="ops-001",
                command_id=f"CMD-{i}",
                fingerprint=f"fp-{i}",
                created_at=datetime.now(timezone.utc),
            )
            return store.create(record)

        with ThreadPoolExecutor(max_workers=10) as pool:
            records = list(pool.map(submit, range(10)))

        winners = {r.command_id for r in records}
        assert len(winners) == 1
        assert store.get("IDEMP-001").command_id in winners
