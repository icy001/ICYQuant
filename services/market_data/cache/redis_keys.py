"""Redis key convention — fixed from day one (Commit 007).

Every component (API, Dashboard, Strategy, Paper Trading) reads and
writes the market cache through these functions — nobody invents
Redis keys ad hoc::

    icyquant:market:quote:{symbol}          latest quality-passed quote
    icyquant:market:bar:{timeframe}:{symbol}  latest 1m bar (live or closed)
    icyquant:market:session:{exchange}      current trading session
    icyquant:market:quality:{symbol}        latest quality verdict

Examples::

    icyquant:market:quote:159852
    icyquant:market:bar:1m:159852
    icyquant:market:session:SZSE
    icyquant:market:quality:159852
"""
from __future__ import annotations

NAMESPACE = "icyquant:market"


def quote_key(symbol: str) -> str:
    return f"{NAMESPACE}:quote:{symbol}"


def bar_key(timeframe: str, symbol: str) -> str:
    return f"{NAMESPACE}:bar:{timeframe}:{symbol}"


def session_key(exchange: str) -> str:
    return f"{NAMESPACE}:session:{exchange}"


def quality_key(symbol: str) -> str:
    return f"{NAMESPACE}:quality:{symbol}"


def quote_pattern() -> str:
    """Pattern matching every cached quote key (inventory scans)."""
    return f"{NAMESPACE}:quote:*"


__all__ = [
    "NAMESPACE",
    "quote_key",
    "bar_key",
    "session_key",
    "quality_key",
    "quote_pattern",
]
