"""Commit 015 §8 — SQLAlchemy implementation of the snapshot repository.

Writes the §8 tables (``account`` / ``account_balance_snapshot`` /
``position_snapshot`` / ``position_snapshot_item``) through the project's
existing session + transaction handling: the caller injects a
``sessionmaker`` (typically ``services.database.SessionFactory`` or a
sync equivalent), so no second connection/transaction scheme is created.

Only the API/server wiring uses this; the default in-memory repository
keeps tests and local dev dependency-free.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from services.account.domain.account import Account
from services.account.domain.balance import AccountBalance
from services.account.domain.enums import as_cst
from services.account.domain.position import Position
from services.account.domain.snapshot import AccountSnapshot

from . import orm


def _dec(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return as_cst(value)
    return value


class SqlAccountSnapshotRepository:
    """Persists §6 snapshots to PostgreSQL (§8).

    ``session_factory`` is any zero-arg callable returning a context-managed
    SQLAlchemy ``Session``.
    """

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    # ── accounts ──────────────────────────────────────────────────────

    def save_account(self, account: Account) -> None:
        with self._session_factory() as session:
            row = (
                session.query(orm.AccountModel)
                .filter_by(account_id=account.account_id)
                .one_or_none()
            )
            if row is None:
                row = orm.AccountModel(account_id=account.account_id)
                session.add(row)
            row.name = account.name
            row.broker = account.broker
            row.currency = account.currency
            row.status = account.status
            session.commit()

    def get_account(self, account_id: str) -> Optional[Account]:
        with self._session_factory() as session:
            row = (
                session.query(orm.AccountModel)
                .filter_by(account_id=account_id)
                .one_or_none()
            )
            return self._account_from_row(row) if row else None

    def accounts(self) -> list[Account]:
        with self._session_factory() as session:
            rows = session.query(orm.AccountModel).order_by(
                orm.AccountModel.account_id
            ).all()
            return [self._account_from_row(r) for r in rows]

    @staticmethod
    def _account_from_row(row: orm.AccountModel) -> Account:
        return Account(
            account_id=row.account_id,
            name=row.name or "",
            broker=row.broker or "",
            currency=row.currency or "CNY",
            status=row.status or "OFFLINE",
            received_timestamp=_aware(row.updated_at),
        )

    # ── snapshots ─────────────────────────────────────────────────────

    def save(self, snapshot: AccountSnapshot) -> AccountSnapshot:
        with self._session_factory() as session:
            if snapshot.sequence == 0:
                # §7 — one past the highest *retained* sequence, never the
                # row count: the count would restart the numbering if the
                # table is ever pruned or back-filled.
                latest = (
                    session.query(orm.PositionSnapshotModel)
                    .filter_by(account_id=snapshot.account_id)
                    .order_by(orm.PositionSnapshotModel.sequence.desc())
                    .first()
                )
                snapshot.sequence = 1 + (
                    (latest.sequence or 0) if latest is not None else 0
                )

            if snapshot.balance is not None:
                session.add(self._balance_row(snapshot))
            session.add(self._header_row(snapshot))
            for position in snapshot.positions:
                session.add(self._item_row(snapshot, position))
            session.commit()
            return snapshot

    def _balance_row(self, snapshot: AccountSnapshot):
        balance = snapshot.balance
        assert balance is not None
        return orm.AccountBalanceSnapshotModel(
            snapshot_id=snapshot.snapshot_id,
            account_id=snapshot.account_id,
            currency=balance.currency,
            cash=balance.cash,
            available_cash=balance.available_cash,
            frozen_cash=balance.frozen_cash,
            market_value=balance.market_value,
            total_asset=balance.total_asset,
            buying_power=balance.buying_power,
            broker_timestamp=_aware(balance.broker_timestamp),
            received_timestamp=_aware(balance.received_timestamp),
            sync_latency_ms=_dec(snapshot.sync_latency_ms),
            source=snapshot.source,
            sequence=snapshot.sequence,
        )

    def _header_row(self, snapshot: AccountSnapshot):
        reconciliation = snapshot.reconciliation or {}
        return orm.PositionSnapshotModel(
            snapshot_id=snapshot.snapshot_id,
            account_id=snapshot.account_id,
            sequence=snapshot.sequence,
            position_count=snapshot.position_count,
            status=snapshot.status,
            source=snapshot.source,
            broker_timestamp=_aware(snapshot.timestamp),
            received_timestamp=_aware(snapshot.received_timestamp),
            sync_latency_ms=_dec(snapshot.sync_latency_ms),
            reconciliation_status=reconciliation.get("status"),
            reconciliation_outcome=reconciliation.get("outcome"),
        )

    def _item_row(self, snapshot: AccountSnapshot, position: Position):
        return orm.PositionSnapshotItemModel(
            snapshot_id=snapshot.snapshot_id,
            account_id=snapshot.account_id,
            symbol=position.symbol,
            exchange=position.exchange,
            quantity=position.quantity,
            available_quantity=position.available_quantity,
            frozen_quantity=position.frozen_quantity,
            average_cost=position.average_cost,
            market_price=position.market_price,
            market_value=position.market_value,
            unrealized_pnl=position.unrealized_pnl,
            unrealized_pnl_pct=position.unrealized_pnl_pct,
            status=position.status,
            broker_timestamp=_aware(position.broker_timestamp),
            received_timestamp=_aware(position.received_timestamp),
        )

    def get(self, snapshot_id: str) -> Optional[AccountSnapshot]:
        with self._session_factory() as session:
            header = (
                session.query(orm.PositionSnapshotModel)
                .filter_by(snapshot_id=snapshot_id)
                .one_or_none()
            )
            if header is None:
                return None
            balance = (
                session.query(orm.AccountBalanceSnapshotModel)
                .filter_by(snapshot_id=snapshot_id)
                .one_or_none()
            )
            return self._snapshot_from_rows(header, balance, header.items)

    def latest(self, account_id: str) -> Optional[AccountSnapshot]:
        rows = self._query_snapshots(account_id, limit=1)
        return rows[0] if rows else None

    def history(self, account_id: str, limit: int = 50) -> list[AccountSnapshot]:
        return self._query_snapshots(account_id, limit=limit)

    def _query_snapshots(self, account_id: str, limit: int) -> list[AccountSnapshot]:
        with self._session_factory() as session:
            query = (
                session.query(orm.PositionSnapshotModel)
                .filter_by(account_id=account_id)
                .order_by(orm.PositionSnapshotModel.sequence.desc())
            )
            if limit and limit > 0:
                query = query.limit(limit)
            headers = query.all()
            if not headers:
                return []
            ids = [h.snapshot_id for h in headers]
            balances = {
                b.snapshot_id: b
                for b in session.query(orm.AccountBalanceSnapshotModel)
                .filter(orm.AccountBalanceSnapshotModel.snapshot_id.in_(ids))
                .all()
            }
            return [
                self._snapshot_from_rows(h, balances.get(h.snapshot_id), h.items)
                for h in headers
            ]

    @staticmethod
    def _snapshot_from_rows(header, balance_row, item_rows) -> AccountSnapshot:
        balance = None
        if balance_row is not None:
            balance = AccountBalance(
                account_id=balance_row.account_id,
                currency=balance_row.currency or "CNY",
                cash=balance_row.cash,
                available_cash=balance_row.available_cash,
                frozen_cash=balance_row.frozen_cash,
                market_value=balance_row.market_value,
                total_asset=balance_row.total_asset,
                buying_power=balance_row.buying_power,
                broker_timestamp=_aware(balance_row.broker_timestamp),
                received_timestamp=_aware(balance_row.received_timestamp),
            )
        positions = [
            Position(
                account_id=row.account_id,
                symbol=row.symbol,
                exchange=row.exchange or "",
                quantity=row.quantity,
                available_quantity=row.available_quantity,
                frozen_quantity=row.frozen_quantity,
                average_cost=row.average_cost,
                market_price=row.market_price,
                market_value=row.market_value,
                unrealized_pnl=row.unrealized_pnl,
                unrealized_pnl_pct=row.unrealized_pnl_pct,
                broker_timestamp=_aware(row.broker_timestamp),
                received_timestamp=_aware(row.received_timestamp),
                status=row.status or "VALID",
            )
            for row in item_rows
        ]
        return AccountSnapshot(
            snapshot_id=header.snapshot_id,
            account_id=header.account_id,
            timestamp=_aware(header.broker_timestamp) or as_cst(header.created_at),
            received_timestamp=_aware(header.received_timestamp)
            or as_cst(header.created_at),
            source=header.source or "BROKER",
            balance=balance,
            positions=positions,
            status=header.status or "SYNCED",
            sequence=header.sequence or 0,
            reconciliation=(
                {
                    "status": header.reconciliation_status,
                    "outcome": header.reconciliation_outcome,
                }
                if header.reconciliation_status
                else None
            ),
        )

    def count(self, account_id: Optional[str] = None) -> int:
        with self._session_factory() as session:
            query = session.query(orm.PositionSnapshotModel)
            if account_id is not None:
                query = query.filter_by(account_id=account_id)
            return query.count()

    def clear(self) -> None:
        with self._session_factory() as session:
            session.query(orm.PositionSnapshotItemModel).delete()
            session.query(orm.PositionSnapshotModel).delete()
            session.query(orm.AccountBalanceSnapshotModel).delete()
            session.query(orm.AccountModel).delete()
            session.commit()


__all__ = ["SqlAccountSnapshotRepository"]
