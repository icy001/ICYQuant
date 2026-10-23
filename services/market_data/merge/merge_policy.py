"""Merge policy — how duplicate bars are resolved (Commit 008).

Rules fixed by the Commit 008 spec:

*   §7 Realtime-priority — for a bar bucket that is not closed yet,
    the realtime version always wins (it is fresher).
*   §8 Closed-bar principle — a *closed* bar should not be silently
    modified.  When history and realtime disagree about the same
    closed bucket the difference is recorded as a ``BarRevision``
    (audit trail), and the realtime value is kept in the unified
    series because it is the system's live view.

Merge identity (§6)::

    symbol + exchange + timeframe + bar_timestamp

    159852 + SZSE + 1m + 10:35  → exactly one bar

Env knobs (never hard-coded):

    MARKET_MERGE_ENABLED    historical merge on/off (default on)
    MARKET_MERGE_MAX_BARS   unified series hard cap (default 500)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class MergeDecision(str, Enum):
    """What the engine kept for one duplicate bar bucket."""

    HISTORICAL = "HISTORICAL"      # historical only (realtime absent)
    REALTIME = "REALTIME"          # realtime kept (fresher, §7)
    BAR_REVISION = "BAR_REVISION"  # closed/closed conflict recorded (§8)


@dataclass(frozen=True)
class BarRevision:
    """One closed-bar disagreement between history and realtime.

    Recorded, never silently dropped — the audit trail for "a
    finalized bar changed" (§8).  ``fields`` maps each differing bar
    field to its historical and realtime values.
    """

    symbol: str
    exchange: str
    timeframe: str
    timestamp: str                      # bar bucket (ISO)
    fields: dict = field(default_factory=dict)
    detected_at: str = ""

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp,
            "fields": {
                name: {"historical": old, "realtime": new}
                for name, (old, new) in self.fields.items()
            },
            "detected_at": self.detected_at,
        }


@dataclass(frozen=True)
class MergePolicy:
    """Configuration for the merge engine."""

    enabled: bool = True
    max_bars: int = 500
    revision_history: int = 20       # revisions kept per symbol
    gap_report_limit: int = 50       # gap ids surfaced per response

    @classmethod
    def from_env(cls) -> "MergePolicy":
        def _env_int(name: str, default: int) -> int:
            raw = os.environ.get(name)
            if raw is None or raw.strip() == "":
                return default
            try:
                return int(raw)
            except ValueError:
                return default

        enabled = os.environ.get(
            "MARKET_MERGE_ENABLED", "true"
        ).strip().lower() in ("1", "true", "yes", "on")
        return cls(
            enabled=enabled,
            max_bars=_env_int("MARKET_MERGE_MAX_BARS", 500),
        )

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "max_bars": self.max_bars,
            "revision_history": self.revision_history,
            "gap_report_limit": self.gap_report_limit,
        }


def revision_now() -> str:
    """Detection timestamp for revisions (UTC ISO)."""
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "MergeDecision",
    "BarRevision",
    "MergePolicy",
    "revision_now",
]
