"""Commit 015 §6 / §9 / §12 / §13 — the account sync orchestrator.

This is the single place the whole §1 chain is assembled::

    BrokerAccountAdapter                    (Commit 015 §5)
            │ raw
    AccountNormalizer                       (§1 / §3 / §13)
            │ AccountBalance / Position
    PositionValuator ← Market Data price    (§18 — one price system)
            │
    AccountSnapshot                         (§6 / §7)
            │
    AccountSnapshotRepository (PostgreSQL)  (§8)
            │
    AccountReconciler ← Position Ledger     (§9 / §10 / §11)
            │
    AccountStateMachine                     (§12)
            │
    API / Dashboard (read-only)             (§15 / §16)

Sandbox rule: nothing here resyncs the broker or rewrites the ledger — a
mismatch is *reported* (§9), and §11's block applies only to new
Shadow/Live orders (:meth:`new_orders_blocked`), never to Paper Trading.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from services.account.domain.account import Account
from services.account.domain.balance import AccountBalance
from services.account.domain.enums import (
    AccountStatus,
    SyncSource,
    as_cst,
    now_cst,
)
from services.account.domain.position import Position
from services.account.domain.snapshot import AccountSnapshot
from services.account.sync.config import AccountSyncConfig
from services.account.sync.exceptions import (
    AccountNotFoundError,
    AccountSnapshotNotFoundError,
    BrokerAccountNotConnectedError,
    InvalidAccountTransition,
)
from services.account.sync.ledger import (
    LedgerBalance,
    LedgerPosition,
    PositionLedgerReader,
)
from services.account.sync.monitoring import AccountSyncMonitor, is_blocking
from services.account.sync.reconciliation import (
    AccountReconciler,
    ReconciliationReport,
)
from services.account.sync.repository import (
    AccountSnapshotRepository,
    InMemoryAccountSnapshotRepository,
)
from services.account.sync.state import AccountStateMachine
from services.account.sync.valuation import (
    MarketDataPriceProvider,
    PositionValuator,
)
from services.broker.account.base import BrokerAccountAdapter
from services.broker.account.broker_account import (
    ProviderBrokerAccountAdapter,
    build_account_provider,
)
from services.broker.account.normalizer import AccountNormalizer
from services.market_data.universe import universe as default_universe

logger = logging.getLogger(__name__)

_T = AccountStatus


class AccountSyncService:
    """Snapshot-sync orchestrator for broker account / positions (§6)."""

    def __init__(
        self,
        adapter: BrokerAccountAdapter,
        repository: Optional[AccountSnapshotRepository] = None,
        *,
        normalizer: Optional[AccountNormalizer] = None,
        ledger: Optional[PositionLedgerReader] = None,
        reconciler: Optional[AccountReconciler] = None,
        valuator: Optional[PositionValuator] = None,
        config: Optional[AccountSyncConfig] = None,
        clock: Optional[Any] = None,
        instruments: Any = None,
        source: str = SyncSource.BROKER.value,
    ) -> None:
        self._adapter = adapter
        self._repository: AccountSnapshotRepository = (
            repository or InMemoryAccountSnapshotRepository()
        )
        self._config = config or getattr(adapter, "config", None) or AccountSyncConfig.from_env()
        instruments = instruments if instruments is not None else default_universe
        self._normalizer = normalizer or AccountNormalizer(
            self._config, instruments=instruments, clock=clock
        )
        self._ledger = ledger
        self._reconciler = reconciler or AccountReconciler(config=self._config)
        self._valuator = valuator or PositionValuator(
            None, enabled=self._config.valuation_enabled
        )
        self._clock = clock
        self._source = str(source)
        self._states: dict[str, AccountStateMachine] = {}
        self._last_successful_sync: dict[str, datetime] = {}
        self._last_latency_ms: dict[str, float] = {}
        self._reports: dict[str, ReconciliationReport] = {}
        self._monitor = AccountSyncMonitor(self)

    # ── accessors ─────────────────────────────────────────────────────

    @property
    def config(self) -> AccountSyncConfig:
        return self._config

    @property
    def adapter(self) -> BrokerAccountAdapter:
        return self._adapter

    @property
    def repository(self) -> AccountSnapshotRepository:
        return self._repository

    @property
    def ledger(self) -> Optional[PositionLedgerReader]:
        return self._ledger

    @property
    def source(self) -> str:
        return self._source

    def now(self) -> datetime:
        if self._clock is not None:
            value = self._clock() if callable(self._clock) else self._clock
            return as_cst(value)
        return now_cst()

    # ── lifecycle (§5 / §12) ──────────────────────────────────────────

    def connect(self) -> None:
        """Open the broker account channel.

        The state machine *and* the persisted account row move together:
        ``GET /accounts`` reports ``connection_state`` next to each
        account's ``status``, so leaving the row behind would make one
        response contradict itself.
        """
        self._adapter.connect()
        for account in self._repository.accounts():
            self._safe_transition(account.account_id, _T.CONNECTED.value)
            self._update_account_status(account.account_id, _T.CONNECTED.value)
        logger.info(
            "account sync connected (provider=%s)", self._adapter.provider_name
        )

    def disconnect(self) -> None:
        """Close the broker account channel."""
        self._adapter.disconnect()
        for account in self._repository.accounts():
            self._safe_transition(account.account_id, _T.OFFLINE.value)
            self._update_account_status(account.account_id, _T.OFFLINE.value)

    def is_connected(self) -> bool:
        return self._adapter.is_connected()

    def connection_state(self) -> str:
        return self._adapter.connection_state()

    # ── accounts ──────────────────────────────────────────────────────

    def register_account(self, account: Account) -> Account:
        """Register an account and start tracking its state (§12)."""
        self._repository.save_account(account)
        machine = self._state_machine(account.account_id)
        if account.status and machine.state == _T.OFFLINE.value:
            if AccountStateMachine.can_transition(_T.OFFLINE.value, account.status):
                self._safe_transition(account.account_id, account.status)
        if self._adapter.is_connected():
            self._safe_transition(account.account_id, _T.CONNECTED.value)
        return self._repository.get_account(account.account_id) or account

    def accounts(self) -> list[Account]:
        return self._repository.accounts()

    def account(self, account_id: str) -> Account:
        account = self._repository.get_account(account_id)
        if account is None:
            raise AccountNotFoundError(
                f"unknown account {account_id!r}", account_id=account_id
            )
        return account

    def _resolve_account_id(self, account_id: Optional[str]) -> Optional[str]:
        if account_id:
            if self._repository.get_account(account_id) is None:
                raise AccountNotFoundError(
                    f"unknown account {account_id!r}", account_id=account_id
                )
            return account_id
        if self._config.account_id:
            return self._config.account_id
        known = self._repository.accounts()
        return known[0].account_id if known else None

    # ── state machine (§12) ───────────────────────────────────────────

    def _state_machine(
        self, account_id: str, initial: Optional[str] = None
    ) -> AccountStateMachine:
        machine = self._states.get(account_id)
        if machine is None:
            machine = AccountStateMachine(account_id, initial=initial)
            self._states[account_id] = machine
        return machine

    def state_machine(self, account_id: str) -> AccountStateMachine:
        return self._state_machine(account_id)

    def state(self, account_id: str) -> str:
        return self._state_machine(account_id).state

    def _safe_transition(self, account_id: str, target: str) -> str:
        machine = self._state_machine(account_id)
        try:
            return machine.to(target)
        except InvalidAccountTransition:
            return machine.force(target)

    def _update_account_status(self, account_id: str, status: str) -> None:
        account = self._repository.get_account(account_id)
        if account is not None:
            self._repository.save_account(account.with_status(status))

    # ── sync (§6 / §9 / §13) ──────────────────────────────────────────

    def sync(self, account_id: Optional[str] = None) -> AccountSnapshot:
        """Pull one account + position snapshot (§6)."""
        resolved = self._resolve_account_id(account_id)
        if resolved is None:
            raise AccountNotFoundError("no account configured for sync")
        machine = self._state_machine(resolved)
        if machine.state == _T.OFFLINE.value and self._adapter.is_connected():
            self._safe_transition(resolved, _T.CONNECTED.value)
        if not self._adapter.is_connected():
            self._safe_transition(resolved, _T.ERROR.value)
            raise BrokerAccountNotConnectedError(
                "account adapter is not connected",
                account_id=resolved,
                state=self._adapter.connection_state(),
            )

        self._safe_transition(resolved, _T.SYNCING.value)
        received = self.now()
        try:
            raw_account = self._adapter.get_account(resolved)
            raw_positions = self._adapter.get_positions(resolved)
        except Exception:
            self._safe_transition(resolved, _T.ERROR.value)
            raise

        # §7 — the sequence comes from the newest *retained* snapshot, not
        # from the retained count: a bounded store (the in-memory repository
        # prunes per account) would otherwise stop counting and start
        # re-using sequences and snapshot ids.
        latest = self._repository.latest(resolved)
        sequence = (latest.sequence + 1) if latest is not None else 1
        snapshot = self._normalizer.normalize_snapshot(
            resolved,
            raw_account,
            raw_positions,
            source=self._source,
            received_timestamp=received,
            sequence=sequence,
        )

        # §18 — one price system: value quantity with Market Data prices.
        snapshot.positions = self._valuator.value_positions(snapshot.positions)
        snapshot.balance = self._valuator.value_balance(
            snapshot.balance, snapshot.positions
        )

        # §9 / §10 — reconcile against the Position Ledger (read-only).
        report: Optional[ReconciliationReport] = None
        if self._ledger is not None:
            report = self._reconciler.reconcile(
                snapshot,
                self._ledger.positions(resolved),
                self._ledger.balance(resolved),
            )
            snapshot.reconciliation = report.as_dict()
            self._reports[resolved] = report

        status = (
            _T.MISMATCH.value
            if report is not None and report.failed
            else _T.SYNCED.value
        )
        snapshot.status = status

        # §7 — persist traceably; §13 — record latency.
        self._repository.save(snapshot)
        self._last_successful_sync[resolved] = received
        if snapshot.sync_latency_ms is not None:
            self._last_latency_ms[resolved] = snapshot.sync_latency_ms
        self._safe_transition(resolved, status)
        self._update_account_status(resolved, status)
        return snapshot

    def sync_all(self) -> list[AccountSnapshot]:
        """Sync every registered account (§6)."""
        return [self.sync(a.account_id) for a in self._repository.accounts()]

    def mark_stale(self, account_id: Optional[str] = None) -> list[str]:
        """Flag accounts whose last sync is older than ``max_sync_age`` (§12)."""
        targets = (
            [account_id]
            if account_id
            else list(self._last_successful_sync.keys())
        )
        marked: list[str] = []
        now = self.now()
        for target in targets:
            last = self._last_successful_sync.get(target)
            if last is None:
                continue
            if (now - last).total_seconds() > self._config.max_sync_age_seconds:
                self._safe_transition(target, _T.STALE.value)
                self._update_account_status(target, _T.STALE.value)
                marked.append(target)
        return marked

    # ── reads (§15 / §16) ─────────────────────────────────────────────

    def latest(self, account_id: str) -> Optional[AccountSnapshot]:
        return self._repository.latest(account_id)

    def require_snapshot(self, account_id: str) -> AccountSnapshot:
        snapshot = self._repository.latest(account_id)
        if snapshot is None:
            raise AccountSnapshotNotFoundError(
                f"no snapshot for account {account_id!r}", account_id=account_id
            )
        return snapshot

    def balance(self, account_id: str) -> AccountBalance:
        snapshot = self.require_snapshot(account_id)
        if snapshot.balance is None:
            raise AccountSnapshotNotFoundError(
                f"snapshot for {account_id!r} carries no balance",
                account_id=account_id,
            )
        return snapshot.balance

    def positions(self, account_id: str) -> list[Position]:
        snapshot = self.require_snapshot(account_id)
        return list(snapshot.positions)

    def snapshots(self, account_id: str, limit: int = 50) -> list[AccountSnapshot]:
        return self._repository.history(account_id, limit=limit)

    def snapshot(self, account_id: str, snapshot_id: str) -> Optional[AccountSnapshot]:
        found = self._repository.get(snapshot_id)
        if found is None or found.account_id != account_id:
            return None
        return found

    def last_successful_sync(self, account_id: str) -> Optional[datetime]:
        return self._last_successful_sync.get(account_id)

    def sync_latency_ms(self, account_id: str) -> Optional[float]:
        return self._last_latency_ms.get(account_id)

    def report(self, account_id: str) -> Optional[ReconciliationReport]:
        return self._reports.get(account_id)

    def reconciliation(self, account_id: str) -> Optional[dict]:
        report = self._reports.get(account_id)
        return report.as_dict() if report else None

    def new_orders_blocked(self, account_id: Optional[str] = None) -> bool:
        """§11 — whether new Shadow/Live orders are blocked.

        Paper Trading is an independent simulated account and is
        deliberately **not** affected.
        """
        if account_id is None:
            if not self._states:
                return False
            return any(is_blocking(m.state) for m in self._states.values())
        return is_blocking(self._state_machine(account_id).state)

    # ── status / health (§14) ─────────────────────────────────────────

    def _empty_status(self) -> dict:
        return {
            "account_id": "",
            "status": _T.OFFLINE.value,
            "connection_state": self._adapter.connection_state(),
            "broker_connected": self._adapter.is_connected(),
            "provider": self._adapter.provider_name,
            "source": self._source,
            "last_successful_sync": None,
            "last_sync_age_seconds": None,
            "sync_latency_ms": None,
            "position_count": 0,
            "mismatch_count": 0,
            "invalid_count": 0,
            "reconciliation_status": None,
            "reconciliation_outcome": None,
            "new_orders_blocked": False,
            "snapshot_count": 0,
        }

    def status(self, account_id: Optional[str] = None) -> dict:
        """Plain facts for :class:`AccountSyncMonitor` (§14)."""
        try:
            resolved = self._resolve_account_id(account_id)
        except AccountNotFoundError:
            if account_id:
                raise
            resolved = None
        if resolved is None:
            return self._empty_status()

        machine = self._state_machine(resolved)
        latest = self._repository.latest(resolved)
        report = self._reports.get(resolved)
        last_sync = self._last_successful_sync.get(resolved)
        age = (self.now() - last_sync).total_seconds() if last_sync else None
        latency = (
            latest.sync_latency_ms
            if latest and latest.sync_latency_ms is not None
            else self._last_latency_ms.get(resolved)
        )
        positions = latest.positions if latest else []
        return {
            "account_id": resolved,
            "status": machine.state,
            "connection_state": self._adapter.connection_state(),
            "broker_connected": self._adapter.is_connected(),
            "provider": self._adapter.provider_name,
            "source": self._source,
            "last_successful_sync": last_sync.isoformat() if last_sync else None,
            "last_sync_age_seconds": age,
            "sync_latency_ms": latency,
            "position_count": len(positions),
            "mismatch_count": report.mismatch_count if report else 0,
            "invalid_count": sum(1 for p in positions if not p.is_valid),
            "reconciliation_status": report.status if report else None,
            "reconciliation_outcome": report.outcome if report else None,
            "new_orders_blocked": is_blocking(machine.state),
            "snapshot_count": self._repository.count(resolved),
        }

    def health(self, account_id: Optional[str] = None) -> dict:
        """§14 health for one account."""
        return self._monitor.health(account_id)

    def health_report(self) -> dict:
        """§14 health for every account + roll-up."""
        return self._monitor.health_report()

    def render_health(self, account_id: Optional[str] = None) -> str:
        """§14 text block."""
        return self._monitor.render(account_id)

    def as_dict(self) -> dict:
        return {
            "provider": self._adapter.provider_name,
            "connection_state": self._adapter.connection_state(),
            "source": self._source,
            "account_count": len(self._repository.accounts()),
            "config": self._config.as_dict(),
        }


# ══════════════════════════════════════════════════════════════════
# Default singleton (API / Dashboard)
# ══════════════════════════════════════════════════════════════════


def demo_ledger(account_id: str = "A001") -> Any:
    """A ledger reader whose positions mirror the simulated provider.

    **Dev-only seeding** so the out-of-the-box Dashboard shows a clean
    ``RECONCILED`` account.  In production the ledger reader points at the
    real Position Ledger (§9) — never at the broker.

    Only *positions* are seeded, deliberately.  A cash leg would have to be
    valued by the same §18 Market Data prices as the broker side to keep
    the ``ACCOUNT_BALANCE`` check meaningful, and a hard-coded number would
    flip the demo to ``MISMATCH`` the moment real quotes arrive.  Leaving
    the balance out means the check is **skipped**, never faked — the
    check itself stays implemented and is covered by the reconciliation
    tests.
    """
    from services.account.sync.ledger import (
        InMemoryPositionLedgerReader,
        LedgerPosition,
    )

    reader = InMemoryPositionLedgerReader()
    reader.set_positions(
        account_id,
        [
            LedgerPosition(
                account_id=account_id,
                symbol="159852",
                quantity=10000,
                available_quantity=10000,
                average_cost="1.25",
            ),
            LedgerPosition(
                account_id=account_id,
                symbol="159559",
                quantity=20000,
                available_quantity=0,
                average_cost="0.80",
            ),
            LedgerPosition(
                account_id=account_id,
                symbol="513050",
                quantity=5000,
                available_quantity=5000,
                average_cost="1.60",
            ),
        ],
    )
    return reader


def build_default_account_service(
    config: Optional[AccountSyncConfig] = None,
    *,
    provider: Any = None,
    ledger: Any = None,
    repository: Optional[AccountSnapshotRepository] = None,
    price_provider: Any = None,
    instruments: Any = None,
    account_id: Optional[str] = None,
) -> AccountSyncService:
    """Wire the simulated provider + in-memory store for the API (§15).

    Valuation is pointed at the unified Market Data service (§18) through a
    lazily-resolved price provider, so the Dashboard shows Price / Market
    Value / P&L without the account package importing the quote pipeline
    at import time.
    """
    config = config or AccountSyncConfig.from_env()
    provider = provider or build_account_provider(config)
    adapter: BrokerAccountAdapter = ProviderBrokerAccountAdapter(provider, config)
    resolved_account_id = account_id or config.account_id or "A001"
    if price_provider is None:
        price_provider = MarketDataPriceProvider()
    service = AccountSyncService(
        adapter,
        repository or InMemoryAccountSnapshotRepository(),
        config=config,
        instruments=instruments if instruments is not None else default_universe,
        ledger=ledger if ledger is not None else demo_ledger(resolved_account_id),
        valuator=PositionValuator(
            price_provider, enabled=config.valuation_enabled
        ),
    )
    service.register_account(
        Account(
            account_id=resolved_account_id,
            name="Simulated A-share account",
            broker=config.provider,
            currency="CNY",
        )
    )
    return service


#: Process-wide default service used by ``apps/api`` and the dashboard.
account_service: AccountSyncService = build_default_account_service()


__all__ = [
    "AccountSyncService",
    "build_default_account_service",
    "demo_ledger",
    "account_service",
    "LedgerPosition",
    "LedgerBalance",
]
