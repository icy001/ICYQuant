"""Commit 015 §7 / §8 — snapshot persistence (the System of Record).

§7 says history is *retained, never overwritten*, and §8 says the store is
a repository behind a contract.  So these suites assert the two properties
that make the audit question answerable — "what did the system believe at
15:00?" — namely: appending never mutates an earlier snapshot, and every
snapshot is addressable by id as long as it is retained.

The in-memory implementation is the one the API singleton and every other
suite run on, so it is tested against the same contract the SQL repository
has to satisfy.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from services.account.domain.account import Account
from services.account.domain.balance import AccountBalance
from services.account.domain.enums import AccountStatus, SyncSource
from services.account.domain.position import Position
from services.account.domain.snapshot import AccountSnapshot
from services.account.sync.repository import (
    AccountSnapshotRepository,
    InMemoryAccountSnapshotRepository,
)

try:  # pragma: no cover - both import paths are supported
    from .helpers import ACCOUNT_ID, LATENCY_MS, T0
except ImportError:  # pragma: no cover
    from helpers import ACCOUNT_ID, LATENCY_MS, T0  # type: ignore[no-redef]

OTHER_ACCOUNT = "A002"
_counter = {"n": 0}


def snapshot(
    account_id: str = ACCOUNT_ID,
    *,
    snapshot_id: str | None = None,
    moment=None,
    sequence: int = 0,
    quantity: str = "10000",
) -> AccountSnapshot:
    """A minimal but complete snapshot — the store never sees a partial one."""
    _counter["n"] += 1
    moment = moment or (T0 + timedelta(seconds=_counter["n"]))
    return AccountSnapshot(
        snapshot_id=snapshot_id or f"{account_id}-{_counter['n']:06d}",
        account_id=account_id,
        timestamp=moment,
        received_timestamp=moment,
        sequence=sequence,
        source=SyncSource.BROKER.value,
        status=AccountStatus.SYNCED.value,
        balance=AccountBalance(
            account_id=account_id,
            cash="83500",
            available_cash="82000",
            frozen_cash="1500",
        ),
        positions=[
            Position(
                account_id=account_id,
                symbol="159852",
                exchange="SZSE",
                quantity=quantity,
                available_quantity=quantity,
                frozen_quantity="0",
                average_cost="1.25",
            )
        ],
    )


def account(account_id: str = ACCOUNT_ID, name: str = "Demo") -> Account:
    return Account(account_id=account_id, name=name, broker="simulated")


@pytest.fixture()
def repo() -> InMemoryAccountSnapshotRepository:
    return InMemoryAccountSnapshotRepository()


# ══════════════════════════════════════════════════════════════════
# §8 — the contract
# ══════════════════════════════════════════════════════════════════


class TestContract:
    def test_the_in_memory_store_satisfies_the_protocol(self, repo):
        assert isinstance(repo, AccountSnapshotRepository)

    def test_every_contract_method_exists(self, repo):
        for name in (
            "save_account",
            "get_account",
            "accounts",
            "save",
            "get",
            "latest",
            "history",
            "count",
            "clear",
        ):
            assert callable(getattr(repo, name))

    def test_an_unknown_account_has_nothing(self, repo):
        assert repo.latest("NOPE") is None
        assert repo.get("NOPE") is None
        assert repo.history("NOPE") == []
        assert repo.count("NOPE") == 0
        assert repo.count() == 0


# ══════════════════════════════════════════════════════════════════
# §7 — append-only history
# ══════════════════════════════════════════════════════════════════


class TestSnapshotHistory:
    def test_saves_append_and_assign_a_sequence(self, repo):
        first = repo.save(snapshot())
        second = repo.save(snapshot())
        third = repo.save(snapshot())
        assert (first.sequence, second.sequence, third.sequence) == (1, 2, 3)
        assert repo.count(ACCOUNT_ID) == 3

    def test_an_explicit_sequence_is_respected(self, repo):
        """The service may compute the sequence from the store's count."""
        explicit = repo.save(snapshot(sequence=42))
        assert explicit.sequence == 42

    def test_history_is_newest_first(self, repo):
        for _ in range(3):
            repo.save(snapshot())
        rows = repo.history(ACCOUNT_ID)
        assert [s.sequence for s in rows] == [3, 2, 1]

    def test_history_can_be_limited_to_the_newest_n(self, repo):
        for _ in range(5):
            repo.save(snapshot())
        rows = repo.history(ACCOUNT_ID, limit=2)
        assert [s.sequence for s in rows] == [5, 4]

    def test_a_zero_limit_returns_nothing(self, repo):
        repo.save(snapshot())
        assert repo.history(ACCOUNT_ID, limit=0) == []

    def test_a_limit_larger_than_the_history_returns_everything(self, repo):
        repo.save(snapshot())
        assert len(repo.history(ACCOUNT_ID, limit=500)) == 1

    def test_latest_is_the_most_recent_snapshot(self, repo):
        repo.save(snapshot())
        newest = repo.save(snapshot())
        assert repo.latest(ACCOUNT_ID) is newest

    def test_lookups_are_scoped_to_the_account_that_owns_them(self, repo):
        mine = repo.save(snapshot(ACCOUNT_ID))
        repo.save(snapshot(OTHER_ACCOUNT))
        assert repo.count(ACCOUNT_ID) == 1
        assert repo.count(OTHER_ACCOUNT) == 1
        assert repo.count() == 2
        assert repo.latest(ACCOUNT_ID).snapshot_id == mine.snapshot_id

    def test_a_snapshot_is_fetchable_by_id(self, repo):
        saved = repo.save(snapshot(snapshot_id="A001-000007-deadbeef"))
        assert repo.get("A001-000007-deadbeef") is saved

    def test_appending_never_mutates_an_earlier_snapshot(self, repo):
        """§7 — the whole point of an append-only store."""
        first = repo.save(snapshot(quantity="10000"))
        repo.save(snapshot(quantity="12000"))
        stored = repo.get(first.snapshot_id)
        assert stored is first
        assert stored.positions[0].quantity == Decimal("10000")
        assert stored.sequence == 1

    def test_ordering_follows_insertion_not_the_timestamp(self, repo):
        """A replay can enqueue an out-of-order vendor stamp; the store's
        order is *when it was recorded*, which is what §13 compares."""
        late = repo.save(snapshot(moment=T0 + timedelta(minutes=5)))
        early = repo.save(snapshot(moment=T0))
        assert repo.latest(ACCOUNT_ID) is early
        assert [s.snapshot_id for s in repo.history(ACCOUNT_ID)] == [
            early.snapshot_id,
            late.snapshot_id,
        ]

    def test_clear_empties_everything(self, repo):
        repo.save(snapshot())
        repo.save_account(account())
        repo.clear()
        assert repo.count() == 0
        assert repo.accounts() == []
        assert repo.latest(ACCOUNT_ID) is None


# ══════════════════════════════════════════════════════════════════
# §7 — bounded retention
# ══════════════════════════════════════════════════════════════════


class TestRetention:
    def test_the_history_is_bounded_per_account(self):
        repo = InMemoryAccountSnapshotRepository(max_history_per_account=3)
        saved = [repo.save(snapshot()) for _ in range(5)]
        assert repo.count(ACCOUNT_ID) == 3
        assert [s.sequence for s in repo.history(ACCOUNT_ID)] == [5, 4, 3]
        # the newest snapshot survives eviction
        assert repo.latest(ACCOUNT_ID) is saved[-1]

    def test_the_sequence_keeps_counting_after_eviction(self):
        """§7 — the numbering is a per-account monotonic counter, so
        pruning the window must not restart it (which would mint duplicate
        sequences and duplicate ``A001-000003-…`` id prefixes)."""
        repo = InMemoryAccountSnapshotRepository(max_history_per_account=2)
        saved = [repo.save(snapshot()) for _ in range(4)]
        assert [s.sequence for s in saved] == [1, 2, 3, 4]
        assert repo.count(ACCOUNT_ID) == 2
        assert repo.latest(ACCOUNT_ID).sequence == 4

    def test_an_explicit_sequence_also_moves_the_counter_forward(self):
        repo = InMemoryAccountSnapshotRepository()
        repo.save(snapshot(sequence=7))
        assert repo.save(snapshot()).sequence == 8

    def test_an_evicted_snapshot_is_no_longer_addressable(self):
        repo = InMemoryAccountSnapshotRepository(max_history_per_account=2)
        old = repo.save(snapshot())
        repo.save(snapshot())
        repo.save(snapshot())
        assert repo.get(old.snapshot_id) is None

    def test_retention_is_per_account(self):
        repo = InMemoryAccountSnapshotRepository(max_history_per_account=2)
        for _ in range(4):
            repo.save(snapshot(ACCOUNT_ID))
        repo.save(snapshot(OTHER_ACCOUNT))
        assert repo.count(ACCOUNT_ID) == 2
        assert repo.count(OTHER_ACCOUNT) == 1

    def test_a_zero_retention_setting_still_keeps_one(self):
        """A store that retained nothing could never answer §7 at all."""
        repo = InMemoryAccountSnapshotRepository(max_history_per_account=0)
        repo.save(snapshot())
        assert repo.count(ACCOUNT_ID) == 1


# ══════════════════════════════════════════════════════════════════
# §8 — the account registry
# ══════════════════════════════════════════════════════════════════


class TestAccountRegistry:
    def test_an_account_round_trips(self, repo):
        repo.save_account(account(name="Simulated A-share account"))
        stored = repo.get_account(ACCOUNT_ID)
        assert stored.account_id == ACCOUNT_ID
        assert stored.name == "Simulated A-share account"

    def test_accounts_are_listed_in_a_stable_order(self, repo):
        repo.save_account(account("B002"))
        repo.save_account(account(ACCOUNT_ID))
        repo.save_account(account("C003"))
        assert [a.account_id for a in repo.accounts()] == [
            ACCOUNT_ID,
            "B002",
            "C003",
        ]

    def test_saving_the_same_account_twice_upserts(self, repo):
        repo.save_account(account(name="first"))
        repo.save_account(account(name="second"))
        assert len(repo.accounts()) == 1
        assert repo.get_account(ACCOUNT_ID).name == "second"

    def test_an_unknown_account_is_none(self, repo):
        assert repo.get_account("NOPE") is None


# ══════════════════════════════════════════════════════════════════
# §7 — the store is not a cache: it keeps what it is given
# ══════════════════════════════════════════════════════════════════


class TestFaithfulStorage:
    def test_a_snapshot_comes_back_unchanged(self, repo):
        saved = repo.save(snapshot())
        stored = repo.latest(ACCOUNT_ID)
        assert stored.snapshot_id == saved.snapshot_id
        assert stored.sync_latency_ms == saved.sync_latency_ms
        assert stored.balance.total_asset == saved.balance.total_asset
        assert stored.positions[0].quantity == saved.positions[0].quantity

    def test_the_receipt_latency_survives_the_round_trip(self, repo):
        moment = T0
        received = T0 + timedelta(milliseconds=LATENCY_MS)
        saved = repo.save(
            AccountSnapshot(
                snapshot_id="A001-000001-latency",
                account_id=ACCOUNT_ID,
                timestamp=moment,
                received_timestamp=received,
            )
        )
        assert saved.sync_latency_ms == LATENCY_MS
        assert repo.latest(ACCOUNT_ID).received_timestamp == received

    def test_an_unreconciled_snapshot_stays_unreconciled(self, repo):
        repo.save(snapshot())
        assert repo.latest(ACCOUNT_ID).reconciliation is None

    def test_the_source_travels_with_the_snapshot(self, repo):
        replayed = AccountSnapshot(
            snapshot_id="A001-000001-replay",
            account_id=ACCOUNT_ID,
            timestamp=T0,
            received_timestamp=T0,
            source=SyncSource.REPLAY.value,
        )
        assert repo.save(replayed).source == SyncSource.REPLAY.value
