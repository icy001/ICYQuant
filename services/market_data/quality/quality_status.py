"""Market data quality status (Commit 006).

The five canonical quality states::

    FRESH       — normal, in-window quote          → trading allowed
    WARNING     — minor quality concern            → config decides
    STALE       — quote age beyond stale line      → trading blocked
    INVALID     — structurally / numerically bad   → trading blocked
    QUARANTINED — suspicious, isolated for review  → trading blocked

Data "received" is not data "trusted": the Quality Gate decides
whether a quote may flow into Strategy / Paper Trading.
"""
from __future__ import annotations

from enum import Enum


class QualityStatus(str, Enum):
    FRESH = "FRESH"
    WARNING = "WARNING"
    STALE = "STALE"
    INVALID = "INVALID"
    QUARANTINED = "QUARANTINED"


__all__ = ["QualityStatus"]
