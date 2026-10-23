"""Broker → MarketQuote normalizer (Commit 014 §3 / §9).

Different brokers return the same reality under different names::

    证券代码  最新价  买一价  卖一价  成交量  成交额  昨收  ...  行情时间

ICYQuant speaks exactly one dialect:

    MarketQuote(symbol, exchange, timestamp, received_timestamp,
                last, bid, ask, bid_size, ask_size, volume,
                turnover, open, high, low, pre_close)

This module is the single translation point::

    券商字段
       ↓
    Broker Adapter
       ↓
    MarketQuote

Contract (§9)
-------------
* The normalizer **parses**, it does not **judge**.  ``last = -1``
  becomes ``Decimal("-1")`` — the Quality Gate decides it is
  ``INVALID_PRICE``.  Nothing is silently clamped, defaulted to 0 or
  rewritten to ``None``; that would destroy the audit trail.
* A payload that cannot be mapped *structurally* (not a mapping, no
  symbol, no price, unparseable timestamp) raises
  :class:`BrokerMessageError` and is dropped by the adapter loop.
* ``received_timestamp`` is stamped by the adapter (the moment the
  frame arrived), so ``MarketQuote.latency_ms`` is meaningful
  (``received - exchange``, §8).

The ``BrokerMarketDataProvider`` SDK is **not** allowed to leak into
``services/market_data/domain`` — only ``MarketQuote`` crosses over.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional, Sequence

from ..domain.instrument import Exchange, Instrument
from ..domain.quote import MarketQuote
from ..exceptions.broker_market_data_error import (
    BrokerErrorCode,
    BrokerMessageError,
)

logger = logging.getLogger(__name__)

#: China Standard Time — A-share exchange timezone (UTC+8, no DST).
try:  # reuse the single source of truth when available
    from ..calendar.trading_calendar import CST as _EXCHANGE_TZ
except Exception:  # pragma: no cover - defensive, calendar is optional here
    from datetime import timedelta

    _EXCHANGE_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")

_SYMBOL_RE = re.compile(r"(\d{6})")

# ── default field aliases ──────────────────────────────────────
#: canonical field → candidate broker keys, highest priority first.
#: English keys are matched case-insensitively; CJK keys exactly.
DEFAULT_FIELDS: dict[str, tuple[str, ...]] = {
    "symbol": ("symbol", "code", "instrument_id", "ticker", "证券代码", "代码"),
    "exchange": ("exchange", "exchange_id", "market", "交易所", "市场"),
    "timestamp": (
        "timestamp",
        "exchange_timestamp",
        "exchange_time",
        "quote_time",
        "time",
        "ts",
        "行情时间",
        "时间",
    ),
    "last": ("last", "last_price", "price", "最新价", "最新价格", "现价"),
    "bid": ("bid", "bid1", "bid_price", "bid1_price", "买一价", "买入价"),
    "ask": ("ask", "ask1", "ask_price", "ask1_price", "卖一价", "卖出价"),
    "bid_size": (
        "bid_size",
        "bid_vol",
        "bid1_size",
        "bid1_vol",
        "买一量",
        "买一量(手)",
        "bid_qty",
    ),
    "ask_size": (
        "ask_size",
        "ask_vol",
        "ask1_size",
        "ask1_vol",
        "卖一量",
        "卖一量(手)",
        "ask_qty",
    ),
    "volume": ("volume", "vol", "total_volume", "成交量", "成交量(手)"),
    "turnover": ("turnover", "amount", "成交额", "成交金额"),
    "open": ("open", "open_price", "开盘", "今开", "开盘价"),
    "high": ("high", "high_price", "最高", "最高价"),
    "low": ("low", "low_price", "最低", "最低价"),
    "pre_close": (
        "pre_close",
        "prev_close",
        "preclose",
        "previous_close",
        "昨收",
        "昨收价",
    ),
}

#: exchange spellings accepted from providers.
EXCHANGE_ALIASES: dict[str, Exchange] = {
    "szse": Exchange.SZSE,
    "sz": Exchange.SZSE,
    "xshe": Exchange.SZSE,
    "shenzhen": Exchange.SZSE,
    "深交所": Exchange.SZSE,
    "深圳": Exchange.SZSE,
    "深圳证券交易所": Exchange.SZSE,
    "sse": Exchange.SSE,
    "sh": Exchange.SSE,
    "shse": Exchange.SSE,
    "xshg": Exchange.SSE,
    "shanghai": Exchange.SSE,
    "上交所": Exchange.SSE,
    "上海": Exchange.SSE,
    "上海证券交易所": Exchange.SSE,
}

_FULL_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y%m%d %H%M%S",
)

_TIME_ONLY_FORMATS = ("%H:%M:%S.%f", "%H:%M:%S", "%H:%M")


def normalize_symbol(value: Any) -> str:
    """Extract the 6-digit A-share code from a vendor symbol field.

    Handles the shapes brokers actually send::

        "159852"      → "159852"
        "SZ159852"    → "159852"
        "159852.SZ"   → "159852"
        "sz-159852"   → "159852"
        159852 (int)  → "159852"

    Raises :class:`BrokerMessageError` (MISSING_SYMBOL) when no 6-digit
    code is present.
    """
    if value is None:
        raise BrokerMessageError(
            "symbol is missing", code=BrokerErrorCode.MISSING_SYMBOL
        )
    if isinstance(value, bool):
        raise BrokerMessageError(
            f"symbol {value!r} is not a valid code",
            code=BrokerErrorCode.MISSING_SYMBOL,
        )
    if isinstance(value, int):
        text = f"{value:06d}"
    else:
        text = str(value).strip()
    match = _SYMBOL_RE.search(text)
    if not match:
        raise BrokerMessageError(
            f"cannot extract 6-digit code from symbol {value!r}",
            code=BrokerErrorCode.MISSING_SYMBOL,
        )
    return match.group(1)


class BrokerQuoteNormalizer:
    """Map raw broker quote payloads to :class:`MarketQuote` (§3).

    Parameters
    ----------
    name:
        Provider name, used only in error context / logs.
    field_map:
        Per-canonical-field key overrides merged over
        :data:`DEFAULT_FIELDS` (e.g. a vendor that calls the last price
        ``"tradePrice"``).
    timezone:
        Exchange timezone applied to naive timestamps (default CST).
    volume_in_lots:
        When the provider reports ``成交`` in 手 (lots), multiply by the
        instrument lot size (100) so ``MarketQuote.volume`` stays in
        shares.  Defaults to ``False`` (shares).
    default_exchange:
        Exchange used when neither the payload nor the code prefix can
        determine it.  ``None`` means "infer, else fail".
    """

    def __init__(
        self,
        *,
        name: str = "broker",
        field_map: Optional[Mapping[str, Sequence[str]]] = None,
        timezone: Optional[timezone] = None,
        volume_in_lots: bool = False,
        default_exchange: Optional[Exchange] = None,
    ) -> None:
        self._name = name
        self._tz = timezone or _EXCHANGE_TZ
        self._volume_in_lots = volume_in_lots
        self._default_exchange = default_exchange

        fields = {k: tuple(v) for k, v in DEFAULT_FIELDS.items()}
        if field_map:
            for canonical, keys in field_map.items():
                fields[canonical] = tuple(keys)
        self._fields = fields

    # ── public API ────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def timezone(self) -> timezone:
        return self._tz

    def normalize(
        self,
        raw: Any,
        *,
        received_timestamp: Optional[datetime] = None,
        trading_date: Optional[date] = None,
    ) -> MarketQuote:
        """Convert one raw payload into a :class:`MarketQuote`.

        Raises
        ------
        BrokerMessageError
            The payload is malformed (not a mapping), or a required
            field (symbol / timestamp / last) is missing or
            unparseable.  A *bad but well-formed* value (``last = -1``)
            is preserved verbatim for the Quality Gate.
        """
        if not isinstance(raw, Mapping):
            raise BrokerMessageError(
                f"expected a mapping payload, got {type(raw).__name__}",
                code=BrokerErrorCode.MALFORMED_MESSAGE,
                provider=self._name,
            )

        index = self._build_index(raw)

        symbol = normalize_symbol(self._pick(index, "symbol"))
        exchange = self._resolve_exchange(index, symbol)

        raw_ts = self._pick(index, "timestamp")
        if raw_ts is None:
            raise BrokerMessageError(
                "exchange timestamp is missing",
                code=BrokerErrorCode.INVALID_TIMESTAMP,
                symbol=symbol,
                provider=self._name,
            )
        timestamp = self._parse_timestamp(raw_ts, symbol, trading_date)

        raw_last = self._pick(index, "last")
        if raw_last is None:
            raise BrokerMessageError(
                "last price is missing",
                code=BrokerErrorCode.MISSING_PRICE,
                symbol=symbol,
                provider=self._name,
            )
        last = self._to_decimal(raw_last, "last", symbol)

        return MarketQuote(
            symbol=symbol,
            exchange=exchange,
            timestamp=timestamp,
            received_timestamp=received_timestamp or datetime.now(timezone.utc),
            last=last,
            bid=self._to_decimal(
                self._pick(index, "bid"), "bid", symbol, default=Decimal("0")
            ),
            ask=self._to_decimal(
                self._pick(index, "ask"), "ask", symbol, default=Decimal("0")
            ),
            bid_size=self._to_int(
                self._pick(index, "bid_size"), "bid_size", symbol
            ),
            ask_size=self._to_int(
                self._pick(index, "ask_size"), "ask_size", symbol
            ),
            volume=self._to_volume(
                self._pick(index, "volume"), symbol
            ),
            turnover=self._to_decimal(
                self._pick(index, "turnover"),
                "turnover",
                symbol,
                default=Decimal("0"),
            ),
            open=self._to_decimal(
                self._pick(index, "open"), "open", symbol, default=Decimal("0")
            ),
            high=self._to_decimal(
                self._pick(index, "high"), "high", symbol, default=Decimal("0")
            ),
            low=self._to_decimal(
                self._pick(index, "low"), "low", symbol, default=Decimal("0")
            ),
            pre_close=self._to_decimal(
                self._pick(index, "pre_close"),
                "pre_close",
                symbol,
                default=Decimal("0"),
            ),
        )

    def as_dict(self) -> dict:
        """Secret-free description for API / Dashboard."""
        return {
            "name": self._name,
            "volume_in_lots": self._volume_in_lots,
            "timezone": str(self._tz),
            "default_exchange": (
                self._default_exchange.value
                if self._default_exchange
                else None
            ),
        }

    # ── field lookup ──────────────────────────────────────────

    @staticmethod
    def _build_index(raw: Mapping) -> dict:
        """Case-insensitive lookup index (ASCII keys lower-cased)."""
        index: dict[str, Any] = {}
        for key, value in raw.items():
            index[key] = value
            if isinstance(key, str) and key.isascii():
                index.setdefault(key.strip().lower(), value)
        return index

    def _pick(self, index: Mapping, canonical: str) -> Any:
        """Return the first non-empty value for a canonical field."""
        for key in self._fields.get(canonical, ()):
            if key in index:
                value = index[key]
                if value is None:
                    continue
                if isinstance(value, str) and value.strip() == "":
                    continue
                return value
        return None

    # ── exchange ──────────────────────────────────────────────

    def _resolve_exchange(self, index: Mapping, symbol: str) -> Exchange:
        raw = self._pick(index, "exchange")
        if isinstance(raw, Exchange):
            return raw
        if raw is not None:
            if isinstance(raw, str):
                token = raw.strip()
                resolved = EXCHANGE_ALIASES.get(token.lower())
                if resolved is None:
                    resolved = EXCHANGE_ALIASES.get(token)
                if resolved is not None:
                    return resolved
            # Unrecognised spelling: fall through to prefix inference.
            logger.warning(
                "%s: unrecognised exchange %r for %s, inferring from code",
                self._name,
                raw,
                symbol,
            )
        return self._infer_exchange(symbol)

    def _infer_exchange(self, symbol: str) -> Exchange:
        try:
            return Instrument.infer_exchange(symbol)
        except ValueError as exc:
            if self._default_exchange is not None:
                return self._default_exchange
            raise BrokerMessageError(
                f"cannot determine exchange for {symbol}: {exc}",
                code=BrokerErrorCode.INVALID_FIELD,
                symbol=symbol,
                provider=self._name,
            ) from exc

    # ── timestamps ────────────────────────────────────────────

    def _parse_timestamp(
        self, value: Any, symbol: str, trading_date: Optional[date]
    ) -> datetime:
        try:
            parsed = self._coerce_timestamp(value, trading_date)
        except BrokerMessageError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalise every failure
            raise BrokerMessageError(
                f"invalid timestamp {value!r}: {exc}",
                code=BrokerErrorCode.INVALID_TIMESTAMP,
                symbol=symbol,
                provider=self._name,
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=self._tz)
        return parsed

    def _coerce_timestamp(
        self, value: Any, trading_date: Optional[date]
    ) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime(value.year, value.month, value.day)
        if isinstance(value, bool):
            raise ValueError("boolean is not a timestamp")
        if isinstance(value, (int, float)):
            return self._from_epoch(float(value))
        if isinstance(value, str):
            return self._from_string(value.strip(), trading_date)
        raise ValueError(f"unsupported timestamp type {type(value).__name__}")

    def _from_epoch(self, number: float) -> datetime:
        magnitude = abs(number)
        if magnitude >= 1e18:  # nanoseconds
            seconds = number / 1e9
        elif magnitude >= 1e15:  # microseconds
            seconds = number / 1e6
        elif magnitude >= 1e12:  # milliseconds
            seconds = number / 1e3
        else:  # seconds
            seconds = number
        return datetime.fromtimestamp(seconds, tz=self._tz)

    def _from_string(self, text: str, trading_date: Optional[date]) -> datetime:
        if text == "":
            raise ValueError("empty timestamp string")

        if text.isdigit():
            length = len(text)
            if length == 14:
                return datetime.strptime(text, "%Y%m%d%H%M%S")
            if length == 12:
                return datetime.strptime(text, "%Y%m%d%H%M")
            if length == 8:
                return datetime.strptime(text, "%Y%m%d")
            if length in (10, 13, 16, 19):
                return self._from_epoch(float(text))
            if length == 6:
                return self._combine_time(
                    datetime.strptime(text, "%H%M%S"), trading_date
                )
            if length == 4:
                return self._combine_time(
                    datetime.strptime(text, "%H%M"), trading_date
                )

        iso_candidate = text.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(iso_candidate)
        except ValueError:
            pass

        for fmt in _FULL_DATETIME_FORMATS:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue

        for fmt in _TIME_ONLY_FORMATS:
            try:
                return self._combine_time(datetime.strptime(text, fmt), trading_date)
            except ValueError:
                continue

        raise ValueError(f"unrecognised timestamp format {text!r}")

    def _combine_time(
        self, parsed: datetime, trading_date: Optional[date]
    ) -> datetime:
        base = trading_date or datetime.now(self._tz).date()
        return datetime(
            base.year,
            base.month,
            base.day,
            parsed.hour,
            parsed.minute,
            parsed.second,
            parsed.microsecond,
            tzinfo=self._tz,
        )

    # ── scalars ───────────────────────────────────────────────

    def _to_decimal(
        self,
        value: Any,
        field: str,
        symbol: str,
        *,
        default: Optional[Decimal] = None,
    ) -> Decimal:
        if value is None:
            if default is not None:
                return default
            raise BrokerMessageError(
                f"{field} is missing",
                code=BrokerErrorCode.MISSING_PRICE,
                symbol=symbol,
                provider=self._name,
            )
        try:
            if isinstance(value, Decimal):
                return value
            if isinstance(value, bool):
                raise InvalidOperation("boolean is not a price")
            text = str(value).strip().replace(",", "")
            return Decimal(text)
        except (InvalidOperation, ValueError) as exc:
            raise BrokerMessageError(
                f"{field}={value!r} is not a number",
                code=BrokerErrorCode.INVALID_FIELD,
                symbol=symbol,
                provider=self._name,
                field=field,
            ) from exc

    def _to_int(
        self, value: Any, field: str, symbol: str, *, default: int = 0
    ) -> int:
        if value is None:
            return default
        try:
            if isinstance(value, bool):
                raise ValueError("boolean is not an integer")
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            text = str(value).strip().replace(",", "")
            return int(Decimal(text))
        except (InvalidOperation, ValueError) as exc:
            raise BrokerMessageError(
                f"{field}={value!r} is not an integer",
                code=BrokerErrorCode.INVALID_FIELD,
                symbol=symbol,
                provider=self._name,
                field=field,
            ) from exc

    def _to_volume(self, value: Any, symbol: str) -> int:
        shares = self._to_int(value, "volume", symbol)
        if self._volume_in_lots and shares:
            shares *= 100
        return shares


__all__ = ["BrokerQuoteNormalizer", "normalize_symbol", "DEFAULT_FIELDS"]
