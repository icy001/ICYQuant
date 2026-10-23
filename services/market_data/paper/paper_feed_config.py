"""Paper Market Feed configuration (Commit 009).

The Paper feed is the bridge between the *real* market data pipeline
(Commits 001–008) and Paper Trading.  Nothing here invents prices —
every knob only decides how strictly the real data is admitted and
how the simulated fill is priced.

All knobs are environment-driven, never hard-coded in business logic::

    PAPER_FEED_ENABLED                master switch              (true)
    PAPER_FEED_SLIPPAGE_BPS           §6 slippage, basis points  (0)
    PAPER_FEED_ALLOW_WARNING_TRADING  §10 WARNING may trade      (false)
    PAPER_FEED_REQUIRE_HEALTHY_CACHE  §12 degraded cache blocks
                                      new orders                 (true)
    PAPER_FEED_ENFORCE_SESSION        §11 session hard gate      (true)
    PAPER_FEED_ENFORCE_QUALITY        §10 quality hard gate      (true)
    PAPER_FEED_ENFORCE_LOT_SIZE       §8 lot size hard gate      (true)
    PAPER_FEED_LOOKAHEAD_TOLERANCE_MS §7 clock-drift tolerance   (0)
    PAPER_FEED_POLL_INTERVAL_S        stream() poll interval     (0.2)

§6 — Phase 1 ships ``slippage_bps = 0`` on purpose: the data chain
must be correct before the fill model gets interesting.  Fixed /
percentage / volatility / volume-impact slippage are explicitly out
of scope for Commit 009; only this single configurable hook exists.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class PaperFeedConfig:
    """Strictness / pricing knobs for the Paper market feed."""

    enabled: bool = True

    # §6 — slippage applied on top of the chosen reference price.
    slippage_bps: float = 0.0

    # §10 — WARNING quotes are refused by default; FRESH always
    # passes, STALE / INVALID / QUARANTINED never do.
    allow_warning_trading: bool = False

    # §12 — Redis is "only" a cache, but a failing cache must not let
    # Paper Trading keep trading blindly.
    require_healthy_cache: bool = True

    # §11 — the trading session is a hard gate, not an advisory.
    enforce_session: bool = True

    # §10 — the quality gate is a hard gate, not an advisory.
    enforce_quality: bool = True

    # §8 — lot size comes from the Instrument Master, not a literal.
    enforce_lot_size: bool = True

    # §7 — how much clock skew is forgiven before a quote that
    # arrived *after* the order counts as lookahead.
    lookahead_tolerance_ms: int = 0

    # stream() polling cadence (the feed itself produces no data).
    poll_interval_s: float = 0.2

    @classmethod
    def from_env(cls) -> "PaperFeedConfig":
        return cls(
            enabled=_env_bool("PAPER_FEED_ENABLED", True),
            slippage_bps=_env_float("PAPER_FEED_SLIPPAGE_BPS", 0.0),
            allow_warning_trading=_env_bool(
                "PAPER_FEED_ALLOW_WARNING_TRADING", False
            ),
            require_healthy_cache=_env_bool(
                "PAPER_FEED_REQUIRE_HEALTHY_CACHE", True
            ),
            enforce_session=_env_bool("PAPER_FEED_ENFORCE_SESSION", True),
            enforce_quality=_env_bool("PAPER_FEED_ENFORCE_QUALITY", True),
            enforce_lot_size=_env_bool("PAPER_FEED_ENFORCE_LOT_SIZE", True),
            lookahead_tolerance_ms=_env_int(
                "PAPER_FEED_LOOKAHEAD_TOLERANCE_MS", 0
            ),
            poll_interval_s=_env_float("PAPER_FEED_POLL_INTERVAL_S", 0.2),
        )

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "slippage_bps": self.slippage_bps,
            "allow_warning_trading": self.allow_warning_trading,
            "require_healthy_cache": self.require_healthy_cache,
            "enforce_session": self.enforce_session,
            "enforce_quality": self.enforce_quality,
            "enforce_lot_size": self.enforce_lot_size,
            "lookahead_tolerance_ms": self.lookahead_tolerance_ms,
            "poll_interval_s": self.poll_interval_s,
        }


__all__ = ["PaperFeedConfig"]
