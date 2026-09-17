"""Shadow Trading configuration (Commit 016 §10 / §16).

Every knob is env-driven, exactly like the Paper feed, cache, quality
and account-sync configs before it.  The baseline (§10) is deliberately
frictionless — zero slippage, zero latency, zero commission — so the
first Shadow runs measure the *decision chain* against real market
data; sensitivity analysis then raises the frictions one at a time::

    slippage  = 0      latency = 0      commission = 0     (baseline)
    slippage  = 5/10/20 bps ...                              (later)

Shadow never re-implements a fill model (§10): the reference price is
the Commit 009 book policy (BUY → ASK / SELL → BID / fallback LAST)
and the values below only add simulated friction on top of it.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from os import getenv
from typing import Optional


def _env_flag(name: str, default: bool) -> bool:
    raw = getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_decimal(name: str, default: str) -> Decimal:
    raw = getenv(name)
    if not raw:
        return Decimal(default)
    try:
        return Decimal(raw)
    except InvalidOperation as exc:  # pragma: no cover - env hygiene
        raise ValueError(f"{name}={raw!r} is not a valid decimal") from exc


@dataclass(frozen=True)
class ShadowConfig:
    """All Shadow Trading knobs in one frozen value."""

    enabled: bool = True
    #: Imaginary starting capital (§16) — user-configured, never the
    #: real broker balance.
    initial_capital: Decimal = Decimal("1000000")
    #: Simulated execution friction (§10), in basis points.
    slippage_bps: float = 0.0
    #: Simulated execution latency (§9), in milliseconds.  The fill may
    #: only use market data visible at ``signal_ts + latency``.
    execution_latency_ms: int = 0
    #: Commission in basis points of traded notional (§10).
    commission_bps: float = 0.0
    #: 0 → a MARKET order fills in one clip; > 0 → the fill is clipped
    #: into chunks of at most this many shares (exercises partial /
    #: multiple fills without inventing a complex fill model).
    max_clip_quantity: int = 0
    #: Single-order notional ceiling enforced by the Shadow risk check.
    max_order_notional: Decimal = Decimal("200000")
    #: Append-only event ledger path (§19).  ``None`` → in-memory only
    #: (tests, API default).  The CLI persists under ``data/shadow/`` so
    #: a Redis outage can never lose Shadow state (§14).
    ledger_path: Optional[str] = None

    @classmethod
    def from_env(cls) -> "ShadowConfig":
        return cls(
            enabled=_env_flag("SHADOW_ENABLED", True),
            initial_capital=_env_decimal("SHADOW_INITIAL_CAPITAL", "1000000"),
            slippage_bps=float(getenv("SHADOW_SLIPPAGE_BPS", "0") or 0),
            execution_latency_ms=int(
                getenv("SHADOW_EXECUTION_LATENCY_MS", "0") or 0
            ),
            commission_bps=float(getenv("SHADOW_COMMISSION_BPS", "0") or 0),
            max_clip_quantity=int(
                getenv("SHADOW_MAX_CLIP_QUANTITY", "0") or 0
            ),
            max_order_notional=_env_decimal(
                "SHADOW_MAX_ORDER_NOTIONAL", "200000"
            ),
            ledger_path=getenv("SHADOW_LEDGER_PATH") or None,
        )

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "initial_capital": str(self.initial_capital),
            "slippage_bps": self.slippage_bps,
            "execution_latency_ms": self.execution_latency_ms,
            "commission_bps": self.commission_bps,
            "max_clip_quantity": self.max_clip_quantity,
            "max_order_notional": str(self.max_order_notional),
            "ledger_path": self.ledger_path,
        }


__all__ = ["ShadowConfig"]
