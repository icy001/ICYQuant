from enum import Enum
from os import getenv


class TradingMode(str, Enum):
    """Runtime trading mode (Commit 016 §4).

    PAPER  — simulated execution on real market data; an independent
             simulated account that real-account reconciliation
             deliberately does not touch.
    SHADOW — the full real decision chain (market data → strategy →
             risk → order intent) with simulated execution only.
             The broker account is a read-only reference; there is no
             code path from Shadow to a broker order API (Commit 016).
    LIVE   — reserved for real broker execution.  It is NOT implemented:
             nothing in the Paper/Shadow code paths may reach it.
    """

    PAPER = "PAPER"
    SHADOW = "SHADOW"
    LIVE = "LIVE"


def get_trading_mode() -> TradingMode:
    mode = getenv("ICYQUANT_MODE", "PAPER").upper()
    return TradingMode(mode)
