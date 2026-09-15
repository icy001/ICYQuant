"""Commit 015 §5 — raw broker account / position payload vocabulary.

An :class:`~services.broker.account.base.BrokerAccountAdapter` returns
the vendor payload **as a mapping** — it does not interpret it.  Mapping
to the standard model is the Normalizer's job (§1), and that is only
possible if the vendor's field names are described in one place.

This module is that place.  Every canonical field carries an alias tuple
covering English, camelCase and the Chinese field names real A-share
gateways return, so a new broker is *data* (`MARKET_*_FIELD_MAP`
overrides / a new alias table), not a code change.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any, Iterable, Mapping, Optional

#: A vendor payload — untrusted, loosely typed.
RawPayload = Mapping[str, Any]


# ── §2 account balance aliases ────────────────────────────────────────

ACCOUNT_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "currency": ("currency", "ccy", "money_type", "币种", "货币"),
    "cash": (
        "cash",
        "total_cash",
        "cash_balance",
        "资金余额",
        "现金",
        "总现金",
    ),
    "available_cash": (
        "available_cash",
        "available",
        "avail_cash",
        "available_amount",
        "enable_balance",
        "可用资金",
        "可用金额",
        "可用余额",
    ),
    "frozen_cash": (
        "frozen_cash",
        "frozen",
        "frozen_amount",
        "frozen_balance",
        "冻结资金",
        "冻结金额",
    ),
    "market_value": (
        "market_value",
        "position_value",
        "securities_value",
        "证券市值",
        "持仓市值",
    ),
    "total_asset": (
        "total_asset",
        "total_assets",
        "total",
        "net_asset",
        "asset",
        "总资产",
        "资产总值",
        "总资产值",
    ),
    "buying_power": (
        "buying_power",
        "purchasing_power",
        "max_buy",
        "buy_amount",
        "可买金额",
        "购买力",
    ),
    "broker_timestamp": (
        "broker_timestamp",
        "timestamp",
        "update_time",
        "updated_at",
        "snapshot_time",
        "时间",
        "更新时间",
        "行情时间",
    ),
}

#: §3 position aliases.
POSITION_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "symbol": (
        "symbol",
        "code",
        "sec_code",
        "security_code",
        "instrument",
        "ticker",
        "证券代码",
        "代码",
    ),
    "exchange": ("exchange", "market", "exchange_id", "交易所", "市场"),
    "quantity": (
        "quantity",
        "qty",
        "volume",
        "position",
        "holding",
        "total_qty",
        "current_amount",
        "持仓数量",
        "证券数量",
        "持仓量",
        "股票余额",
    ),
    "available_quantity": (
        "available_quantity",
        "available",
        "avail_qty",
        "enable_amount",
        "available_amount",
        "sellable",
        "可用数量",
        "可卖数量",
        "可用余额",
    ),
    "frozen_quantity": (
        "frozen_quantity",
        "frozen",
        "frozen_qty",
        "frozen_amount",
        "冻结数量",
        "冻结量",
    ),
    "average_cost": (
        "average_cost",
        "avg_cost",
        "cost",
        "cost_price",
        "open_price",
        "成本价",
        "持仓成本",
        "成本",
    ),
    "market_price": (
        "market_price",
        "price",
        "last_price",
        "current_price",
        "现价",
        "市价",
        "最新价",
        "当前价",
    ),
    "market_value": (
        "market_value",
        "value",
        "position_value",
        "市值",
        "证券市值",
        "持仓市值",
    ),
    "broker_timestamp": (
        "broker_timestamp",
        "timestamp",
        "update_time",
        "时间",
        "更新时间",
    ),
}

#: Fields a position cannot be built without (§3).
POSITION_REQUIRED_FIELDS: tuple[str, ...] = ("symbol", "quantity")

#: Fields an account balance is built from when present.
ACCOUNT_FIELDS: tuple[str, ...] = tuple(ACCOUNT_FIELD_ALIASES)
POSITION_FIELDS: tuple[str, ...] = tuple(POSITION_FIELD_ALIASES)


def normalize_key(key: Any) -> str:
    """Fold a vendor key for tolerant matching.

    ``"Available_Cash"``, ``"available-cash"`` and ``"可用资金"`` all
    survive case / separator differences.
    """
    text = str(key).strip().lower()
    for ch in (" ", "_", "-", ".", "\t"):
        text = text.replace(ch, "")
    return text


def as_mapping(payload: Any) -> dict[str, Any]:
    """Coerce a payload into a plain mapping.

    Accepts a ``Mapping``, a dataclass instance or any object with a
    public ``__dict__`` — real provider SDKs frequently hand back a
    response object rather than a dict.
    """
    if payload is None:
        return {}
    if isinstance(payload, Mapping):
        return dict(payload)
    if is_dataclass(payload) and not isinstance(payload, type):
        return {f.name: getattr(payload, f.name) for f in fields(payload)}
    if hasattr(payload, "__dict__"):
        return {
            str(k): v for k, v in vars(payload).items() if not str(k).startswith("_")
        }
    raise TypeError(f"cannot read broker payload of type {type(payload)!r}")


def resolve_field(
    payload: Any,
    canonical: str,
    aliases: Mapping[str, Iterable[str]],
    default: Any = None,
) -> Any:
    """Find ``canonical`` in ``payload`` via its alias table.

    Resolution order: exact key, then case/separator-folded alias match.
    Returns ``default`` when absent — never fabricates a value.
    """
    mapping = as_mapping(payload)
    if canonical in mapping:
        return mapping[canonical]
    wanted = {normalize_key(canonical)}
    for alias in aliases.get(canonical, ()):
        wanted.add(normalize_key(alias))
    for key, value in mapping.items():
        if normalize_key(key) in wanted:
            return value
    return default


def resolve_fields(
    payload: Any,
    aliases: Mapping[str, Iterable[str]],
    keys: Optional[Iterable[str]] = None,
) -> dict[str, Any]:
    """Resolve every key (default: all known for the alias table)."""
    selected = tuple(keys) if keys is not None else tuple(aliases)
    return {key: resolve_field(payload, key, aliases) for key in selected}


def missing_fields(
    payload: Any,
    required: Iterable[str],
    aliases: Mapping[str, Iterable[str]],
) -> list[str]:
    """Required canonical fields absent from ``payload``."""
    return [
        field
        for field in required
        if resolve_field(payload, field, aliases) is None
    ]


def extra_fields(
    payload: Any,
    aliases: Mapping[str, Iterable[str]],
) -> dict[str, Any]:
    """Vendor keys that matched no canonical alias (kept for audit §7)."""
    mapping = as_mapping(payload)
    known = {
        normalize_key(alias)
        for alias_list in aliases.values()
        for alias in alias_list
    }
    known |= {normalize_key(canonical) for canonical in aliases}
    return {
        key: value
        for key, value in mapping.items()
        if normalize_key(key) not in known
    }


__all__ = [
    "RawPayload",
    "ACCOUNT_FIELD_ALIASES",
    "POSITION_FIELD_ALIASES",
    "ACCOUNT_FIELDS",
    "POSITION_FIELDS",
    "POSITION_REQUIRED_FIELDS",
    "normalize_key",
    "as_mapping",
    "resolve_field",
    "resolve_fields",
    "missing_fields",
    "extra_fields",
]
