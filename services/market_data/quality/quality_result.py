"""MarketDataQualityResult — the unified quality verdict (Commit 006).

Every quote (and bar) passing through the Quality Gate returns one
result object::

    MarketDataQualityResult
    ├── status        FRESH / WARNING / STALE / INVALID / QUARANTINED
    ├── checks        name → passed, one row per executed check
    ├── reasons       machine-readable failure codes
    ├── quote_age_ms  exchange-timestamp age at check time
    ├── latency_ms    received - exchange timestamp
    └── checked_at    when the gate ran

Derived semantics:

    passed    — may the data enter the normal quote stream?
                (INVALID / QUARANTINED / duplicates are rejected)
    tradable  — may Strategy / Paper Trading act on it?
                (FRESH always; WARNING only if configured; never
                STALE / INVALID / QUARANTINED)
    action    — the single gate verdict for the pipeline:
                PASS / BLOCK_TRADING / DROP / QUARANTINE
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .quality_status import QualityStatus


@dataclass(frozen=True)
class MarketDataQualityResult:
    """Outcome of one Quality Gate evaluation."""

    symbol: str
    status: QualityStatus
    checks: dict[str, bool] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    quote_age_ms: int = 0
    latency_ms: int = 0
    checked_at: Optional[datetime] = None
    # WARNING quotes may open new positions only when configured
    # ("WARNING → 默认不产生新订单" is the conservative default).
    allow_warning_trading: bool = False

    # ── derived semantics ──────────────────────────────────────

    @property
    def quarantined(self) -> bool:
        """The gate isolated this data for review."""
        return self.status is QualityStatus.QUARANTINED

    @property
    def passed(self) -> bool:
        """Data may enter the normal quote stream.

        STALE quotes still pass (they are valid data, merely old —
        the QuoteService keeps them for display); INVALID,
        QUARANTINED and duplicates are rejected outright.
        """
        return self.status not in (
            QualityStatus.INVALID,
            QualityStatus.QUARANTINED,
        ) and "DUPLICATE" not in self.reasons

    @property
    def tradable(self) -> bool:
        """Strategy Gate: may new orders be produced from this data?

        FRESH always; WARNING only when configured to allow it;
        STALE / INVALID / QUARANTINED never.
        """
        if self.status is QualityStatus.FRESH:
            return True
        if self.status is QualityStatus.WARNING:
            return self.allow_warning_trading
        return False

    @property
    def action(self) -> str:
        """The single pipeline action for this verdict."""
        if "DUPLICATE" in self.reasons:
            return "DROP"
        if self.status is QualityStatus.QUARANTINED:
            return "QUARANTINE"
        if self.status is QualityStatus.INVALID:
            return "BLOCK_TRADING"
        if self.status is QualityStatus.STALE:
            return "BLOCK_TRADING"
        return "PASS"

    @property
    def reasons_summary(self) -> str:
        return ", ".join(self.reasons) if self.reasons else "ok"

    def as_dict(self) -> dict:
        """Serializable view."""
        return {
            "symbol": self.symbol,
            "status": self.status.value,
            "passed": self.passed,
            "tradable": self.tradable,
            "action": self.action,
            "checks": dict(self.checks),
            "reasons": list(self.reasons),
            "quote_age_ms": self.quote_age_ms,
            "latency_ms": self.latency_ms,
            "checked_at": (
                self.checked_at.isoformat() if self.checked_at else None
            ),
        }


__all__ = ["MarketDataQualityResult"]
