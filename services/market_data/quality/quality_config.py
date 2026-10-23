"""Quality Gate configuration (Commit 006).

All thresholds are configurable — never hard-coded in business logic:

    MARKET_DATA_FRESH_MS     age below this            → FRESH   (3000)
    MARKET_DATA_WARNING_MS   age above FRESH, below
                             the stale line           → WARNING (10000)
    MARKET_DATA_STALE_MS     stale line; age at/above  → STALE   (10000)

When MARKET_DATA_STALE_MS is set explicitly it overrides the stale
line; otherwise the stale line equals the warning threshold (the
classic 3s / 10s two-line scheme from Commit 003).

Additional knobs:

    MARKET_DATA_FUTURE_TOLERANCE_MS   clock-drift tolerance for
                                      future-timestamp rejection
    MARKET_DATA_OUTLIER_PCT           price deviation (percent)
                                      beyond which a quote is
                                      quarantined (marked, never
                                      modified) — real limit-up /
                                      resumption moves survive as
                                      QUARANTINED, not INVALID
    MARKET_DATA_ALLOW_WARNING_TRADING whether WARNING quotes may
                                      still open new positions
                                      (default false — "WARNING
                                      produces no new orders")
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


def _env_int(name: str, default: Optional[int] = None) -> Optional[int]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_decimal_pct(name: str, default: float) -> Decimal:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return Decimal(str(default))
    try:
        return Decimal(raw)
    except Exception:
        return Decimal(str(default))


@dataclass(frozen=True)
class QualityConfig:
    """Thresholds for the market data quality gate."""

    fresh_ms: int = 3000
    warning_ms: int = 10000
    stale_ms: int = 10000
    future_tolerance_ms: int = 5000
    outlier_pct: Decimal = Decimal("30")   # percent, e.g. 30 → ±30%
    allow_warning_trading: bool = False
    duplicate_window: int = 4096           # remembered quote identities

    @property
    def stale_line_ms(self) -> int:
        """Effective stale line (explicit stale_ms wins)."""
        return self.stale_ms

    @classmethod
    def from_env(cls) -> "QualityConfig":
        """Build the config from MARKET_DATA_* environment variables."""
        fresh = _env_int("MARKET_DATA_FRESH_MS", 3000)
        warning = _env_int("MARKET_DATA_WARNING_MS", 10000)
        stale = _env_int("MARKET_DATA_STALE_MS", warning)
        future = _env_int("MARKET_DATA_FUTURE_TOLERANCE_MS", 5000)
        outlier = _env_decimal_pct("MARKET_DATA_OUTLIER_PCT", 30)
        allow_warn = os.environ.get(
            "MARKET_DATA_ALLOW_WARNING_TRADING", ""
        ).strip().lower() in ("1", "true", "yes", "on")
        return cls(
            fresh_ms=fresh,
            warning_ms=warning,
            stale_ms=stale,
            future_tolerance_ms=future,
            outlier_pct=outlier,
            allow_warning_trading=allow_warn,
        )

    def as_dict(self) -> dict:
        return {
            "fresh_ms": self.fresh_ms,
            "warning_ms": self.warning_ms,
            "stale_ms": self.stale_ms,
            "future_tolerance_ms": self.future_tolerance_ms,
            "outlier_pct": str(self.outlier_pct),
            "allow_warning_trading": self.allow_warning_trading,
        }


__all__ = ["QualityConfig"]
