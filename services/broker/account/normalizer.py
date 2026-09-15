"""Commit 015 §1 / §3 / §13 / §19 — broker payload → standard model.

The normalizer is the *only* place a vendor field name is interpreted::

    Broker Account Adapter  (raw mapping)
            │
            ▼
    AccountNormalizer       (→ AccountBalance / Position / AccountSnapshot)
            │
            ▼
    Validation              (consistency, §3)
            │
            ▼
    PostgreSQL System of Record

Rules it follows to the letter:

* **§3 — no silent repair.**  ``quantity != available + frozen`` yields a
  ``Position`` marked ``INVALID``; the reconciler/exceptions channel
  handles it.  Numbers are never nudged to agree.
* **§19 — T+1.**  ``available_quantity`` is taken as the broker reported
  it.  Only when the broker omits it *and* gives ``frozen`` do we use
  the arithmetic ``available = quantity − frozen``; when both are absent
  the position is ``INVALID`` rather than guessed.
* **§13 — time.**  Both ``broker_timestamp`` and ``received_timestamp``
  are retained so ``sync_latency`` is real; the vendor's own stale
  timestamp is never overwritten with ``local_now()``.
* **§18 — one price system.**  The normalizer does **not** set
  ``market_price`` / ``market_value``: valuation belongs to the Market
  Data pipeline, so a broker's price can never disagree with ICYQuant's.
* **§21 — universe.**  An unknown symbol is rejected, not stored.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable, Mapping, Optional

from services.account.domain.balance import AccountBalance
from services.account.domain.enums import CST, SyncSource, as_cst, now_cst
from services.account.domain.position import Position
from services.account.domain.snapshot import AccountSnapshot
from services.account.domain.values import money, quantity as to_qty
from services.account.sync.config import AccountSyncConfig
from services.account.sync.exceptions import (
    AccountNormalizationError,
    UnknownAccountSymbolError,
)
from services.market_data.domain.instrument import Exchange, Instrument

from .models import (
    ACCOUNT_FIELD_ALIASES,
    POSITION_FIELD_ALIASES,
    POSITION_REQUIRED_FIELDS,
    missing_fields,
    resolve_field,
)

#: A-share lot size — 1 手 == 100 份.
LOT_SIZE = Decimal("100")

_TIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y%m%d%H%M%S",
    "%Y%m%d",
    "%H:%M:%S",
)


class AccountNormalizer:
    """Maps raw broker account / position payloads to the domain (§1)."""

    def __init__(
        self,
        config: Optional[AccountSyncConfig] = None,
        *,
        instruments: Any = None,
        clock: Optional[Any] = None,
        account_aliases: Optional[Mapping[str, Iterable[str]]] = None,
        position_aliases: Optional[Mapping[str, Iterable[str]]] = None,
    ) -> None:
        self._config = config or AccountSyncConfig.from_env()
        #: Instrument Master (Universe) — validates symbols (§21).
        self._instruments = instruments
        self._clock = clock
        self._account_aliases = {
            **ACCOUNT_FIELD_ALIASES,
            **dict(account_aliases or {}),
        }
        self._position_aliases = {
            **POSITION_FIELD_ALIASES,
            **dict(position_aliases or {}),
        }

    # ── helpers ───────────────────────────────────────────────────────

    @property
    def config(self) -> AccountSyncConfig:
        return self._config

    def _now(self) -> datetime:
        if self._clock is not None:
            value = self._clock() if callable(self._clock) else self._clock
            return as_cst(value)
        return now_cst()

    def parse_timestamp(self, value: Any) -> Optional[datetime]:
        """Parse a vendor timestamp (§13).

        Accepts a ``datetime``, an ISO / ``YYYY-MM-DD HH:MM:SS`` string,
        or an epoch int/float (seconds or milliseconds).
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return as_cst(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            epoch = float(value)
            if epoch > 1e11:  # milliseconds
                epoch /= 1000.0
            try:
                return datetime.fromtimestamp(epoch, CST)
            except (OverflowError, OSError, ValueError):
                return None
        text = str(value).strip()
        if not text:
            return None
        if text.isdigit() and len(text) >= 10:
            try:
                epoch = float(text)
                if epoch > 1e11:
                    epoch /= 1000.0
                return datetime.fromtimestamp(epoch, CST)
            except (OverflowError, OSError, ValueError):
                pass
        candidate = text.replace("/", "-")
        try:
            return as_cst(datetime.fromisoformat(candidate.replace(" ", "T")))
        except ValueError:
            pass
        for fmt in _TIME_FORMATS:
            try:
                parsed = datetime.strptime(candidate, fmt)
            except ValueError:
                continue
            if fmt == "%H:%M:%S":
                today = self._now()
                parsed = parsed.replace(
                    year=today.year, month=today.month, day=today.day
                )
            return as_cst(parsed)
        return None

    def normalize_symbol(self, raw: Any) -> tuple[str, str]:
        """Return ``(symbol, exchange)`` for a vendor code (§21).

        Handles ``"159852"``, ``"159852.SZ"``, ``"SZ.159852"`` and
        ``"159852.SZSE"``.  An unknown symbol is rejected when strict.
        """
        if raw is None or str(raw).strip() == "":
            raise AccountNormalizationError("position has no symbol")
        text = str(raw).strip().upper()
        code = text
        suffix = ""
        if "." in text:
            left, _, right = text.partition(".")
            if left.isdigit():
                code, suffix = left, right
            else:
                code, suffix = right, left
        code = code.strip()
        if not (len(code) == 6 and code.isdigit()):
            raise AccountNormalizationError(f"invalid A-share code: {raw!r}")

        instrument = None
        if self._instruments is not None:
            instrument = self._instruments.get(code)
            if instrument is None:
                if self._config.strict_symbols:
                    raise UnknownAccountSymbolError(
                        f"symbol {code!r} is not in the Instrument Master (§21)",
                        symbol=code,
                    )
                instrument = None

        if instrument is not None:
            return code, instrument.exchange.value

        exchange = self._infer_exchange(code, suffix)
        return code, exchange

    def _infer_exchange(self, code: str, suffix: str) -> str:
        suffix = (suffix or "").upper()
        if suffix in ("SZ", "SZSE", "深圳"):
            return Exchange.SZSE.value
        if suffix in ("SH", "SSE", "上海"):
            return Exchange.SSE.value
        try:
            return Instrument.infer_exchange(code).value
        except ValueError:
            # e.g. a 5xx code the seed universe does not list.
            if code.startswith("5"):
                return Exchange.SSE.value
            if code.startswith("1"):
                return Exchange.SZSE.value
            raise UnknownAccountSymbolError(
                f"cannot infer exchange for code {code!r}", symbol=code
            ) from None

    def _scale_quantity(self, value: Any) -> Decimal:
        amount = to_qty(value)
        if self._config.volume_in_lots:
            amount = amount * LOT_SIZE
        return amount

    # ── account balance (§2 / §3) ─────────────────────────────────────

    def normalize_account(
        self,
        payload: Any,
        *,
        account_id: Optional[str] = None,
        received_timestamp: Optional[datetime] = None,
    ) -> AccountBalance:
        """Map a raw balance payload to :class:`AccountBalance` (§2)."""
        received = as_cst(received_timestamp) if received_timestamp else self._now()
        resolved = {
            key: resolve_field(payload, key, self._account_aliases)
            for key in self._account_aliases
        }
        resolved_account_id = (
            account_id
            or resolve_field(payload, "account_id", self._account_aliases)
            or self._config.account_id
        )
        if not resolved_account_id:
            raise AccountNormalizationError(
                "account payload carries no account id"
            )
        broker_timestamp = self.parse_timestamp(resolved.get("broker_timestamp"))
        balance = AccountBalance(
            account_id=str(resolved_account_id),
            currency=str(resolved.get("currency") or "CNY"),
            cash=resolved.get("cash"),
            available_cash=resolved.get("available_cash"),
            frozen_cash=resolved.get("frozen_cash"),
            market_value=resolved.get("market_value"),
            total_asset=resolved.get("total_asset"),
            buying_power=resolved.get("buying_power"),
            broker_timestamp=broker_timestamp,
            received_timestamp=received,
        )
        return balance.derive_missing()

    # ── positions (§3 / §19 / §21) ────────────────────────────────────

    def normalize_position(
        self,
        payload: Any,
        *,
        account_id: str,
        received_timestamp: Optional[datetime] = None,
    ) -> Position:
        """Map a raw position payload to :class:`Position` (§3)."""
        received = as_cst(received_timestamp) if received_timestamp else self._now()
        missing = missing_fields(
            payload, POSITION_REQUIRED_FIELDS, self._position_aliases
        )
        if missing:
            raise AccountNormalizationError(
                "position payload missing required field(s): "
                + ", ".join(missing)
            )

        symbol, exchange = self.normalize_symbol(
            resolve_field(payload, "symbol", self._position_aliases)
        )
        raw_exchange = resolve_field(payload, "exchange", self._position_aliases)
        if raw_exchange and not self._instruments:
            exchange = self._infer_exchange(symbol, str(raw_exchange))

        qty = self._scale_quantity(
            resolve_field(payload, "quantity", self._position_aliases)
        )
        frozen_raw = resolve_field(payload, "frozen_quantity", self._position_aliases)
        avail_raw = resolve_field(
            payload, "available_quantity", self._position_aliases
        )
        if avail_raw is not None:
            available = self._scale_quantity(avail_raw)
        elif frozen_raw is not None:
            # §19: never `available = quantity`; the frozen split is the
            # broker's own arithmetic, so deriving available is exact.
            available = qty - self._scale_quantity(frozen_raw)
        else:
            # The broker told us the holding but not one word about how
            # much of it is sellable.  `available = quantity` is the bug
            # §19 names, and `available = 0 / frozen = quantity` is just
            # as much of an invention that would silently pass every
            # consistency check — so the split stays unknown and the
            # position is reported INVALID below.
            available = Decimal("0")
        if frozen_raw is not None:
            frozen = self._scale_quantity(frozen_raw)
        else:
            frozen = qty - available
        split_unknown = avail_raw is None and frozen_raw is None

        average_cost = money(
            resolve_field(payload, "average_cost", self._position_aliases)
        )
        broker_timestamp = self.parse_timestamp(
            resolve_field(payload, "broker_timestamp", self._position_aliases)
        )

        position = Position(
            account_id=str(account_id),
            symbol=symbol,
            exchange=exchange,
            quantity=qty,
            available_quantity=available,
            frozen_quantity=frozen,
            average_cost=average_cost,
            # §18: valuation is Market Data's job — deliberately left None.
            market_price=None,
            market_value=None,
            unrealized_pnl=None,
            unrealized_pnl_pct=None,
            broker_timestamp=broker_timestamp,
            received_timestamp=received,
        )
        # §3 / §19 — two ways a position ends up INVALID: the split the
        # broker sent does not add up, or the broker never sent a split.
        # Either way the numbers are kept exactly as reported and the
        # verdict travels with them; nothing is repaired in place.
        if not position.consistent or split_unknown:
            position = position.as_invalid()
        return position

    def normalize_positions(
        self,
        payloads: Iterable[Any],
        *,
        account_id: str,
        received_timestamp: Optional[datetime] = None,
    ) -> list[Position]:
        """Map every raw position payload (§3)."""
        received = as_cst(received_timestamp) if received_timestamp else self._now()
        return [
            self.normalize_position(
                payload, account_id=account_id, received_timestamp=received
            )
            for payload in payloads
        ]

    # ── snapshot (§6 / §7) ────────────────────────────────────────────

    def normalize_snapshot(
        self,
        account_id: str,
        account_payload: Any,
        position_payloads: Iterable[Any],
        *,
        source: str = SyncSource.BROKER.value,
        received_timestamp: Optional[datetime] = None,
        snapshot_id: Optional[str] = None,
        sequence: int = 0,
    ) -> AccountSnapshot:
        """Assemble one :class:`AccountSnapshot` from raw payloads (§6)."""
        received = as_cst(received_timestamp) if received_timestamp else self._now()
        balance = self.normalize_account(
            account_payload, account_id=account_id, received_timestamp=received
        )
        positions = self.normalize_positions(
            position_payloads, account_id=account_id, received_timestamp=received
        )
        broker_timestamp = balance.broker_timestamp
        if broker_timestamp is None:
            stamps = [p.broker_timestamp for p in positions if p.broker_timestamp]
            broker_timestamp = min(stamps) if stamps else received
        return AccountSnapshot(
            snapshot_id=snapshot_id or self.new_snapshot_id(account_id, sequence),
            account_id=str(account_id),
            timestamp=broker_timestamp,
            received_timestamp=received,
            source=str(source),
            # §7 — carry the sequence the id was minted with, so the
            # number in ``A001-000004-…`` and ``snapshot.sequence`` can
            # never disagree.  ``0`` means "the store assigns it".
            sequence=sequence or 0,
            balance=balance,
            positions=positions,
        )

    @staticmethod
    def new_snapshot_id(account_id: str, sequence: int = 0) -> str:
        """A traceable, collision-free snapshot id (§7)."""
        return f"{account_id}-{sequence:06d}-{uuid.uuid4().hex[:8]}"


__all__ = ["AccountNormalizer"]
