"""A-share ETF / LOF instrument model.

The 11 seed symbols (159852, 513050, ...) are NOT all ETFs — some
are QDII-ETFs, some are LOFs.  InstrumentType distinguishes them so
downstream strategy / risk code can treat them differently (e.g.
QDII products have different trading hours and T+2 settlement).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional


class InstrumentType(str, Enum):
    """A-share fund instrument types."""

    ETF = "ETF"
    QDII_ETF = "QDII-ETF"
    LOF = "LOF"
    QDII_LOF = "QDII-LOF"


class Exchange(str, Enum):
    """A-share exchanges where ETFs / LOFs are listed."""

    SZSE = "SZSE"  # Shenzhen
    SSE = "SSE"    # Shanghai


class TradingStatus(str, Enum):
    """Instrument trading status (mirrors exchange feed)."""

    NORMAL = "NORMAL"        # continuous trading
    HALTED = "HALTED"        # temporarily halted
    SUSPENDED = "SUSPENDED"  # long-term suspension
    DELISTED = "DELISTED"


@dataclass(frozen=True)
class Instrument:
    """A single tradable A-share fund instrument.

    Commit 002 extends the model with tick_size and enabled fields
    for the Instrument Master / Universe registry.
    """

    symbol: str
    exchange: Exchange
    instrument_type: InstrumentType
    currency: str = "CNY"
    lot_size: int = 100
    trading_status: TradingStatus = TradingStatus.NORMAL
    name: str = ""
    tick_size: Decimal = Decimal("0.001")
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")

    @staticmethod
    def infer_exchange(symbol: str) -> Exchange:
        """Infer exchange from A-share fund code prefix.

        SZSE ETF/LOF: 15xxxx, 16xxxx
        SSE ETF/LOF:  50xxxx, 51xxxx
        """
        if not symbol or len(symbol) != 6:
            raise ValueError(f"invalid A-share fund code: {symbol!r}")
        if symbol.startswith(("15", "16")):
            return Exchange.SZSE
        if symbol.startswith(("50", "51")):
            return Exchange.SSE
        raise ValueError(
            f"cannot infer exchange for code {symbol!r} "
            f"(expected 15/16/50/51 prefix)"
        )

    @staticmethod
    def infer_type(symbol: str, name: str = "") -> InstrumentType:
        """Heuristic type inference from symbol + name.

        Accurate classification requires the fund prospectus; this
        heuristic covers the 11 seed symbols and common patterns.
        Phase 2 (Instrument Master) will store authoritative types.
        """
        # Known QDII-ETFs (cross-border, tracks overseas index)
        qdii_etf_codes = {"513050", "513310"}
        # Known QDII-LOFs
        qdii_lof_codes = {"165520", "501225", "161116"}
        # Known LOFs (not QDII)
        lof_codes = set()

        if symbol in qdii_etf_codes:
            return InstrumentType.QDII_ETF
        if symbol in qdii_lof_codes:
            return InstrumentType.QDII_LOF
        if symbol in lof_codes:
            return InstrumentType.LOF

        # Heuristic: 15xxxx on SZSE = ETF, 16xxxx = LOF
        #            51xxxx on SSE = ETF, 50xxxx = LOF or QDII-ETF
        if symbol.startswith("15"):
            return InstrumentType.ETF
        if symbol.startswith("16"):
            return InstrumentType.LOF
        if symbol.startswith("51"):
            return InstrumentType.ETF
        if symbol.startswith("50"):
            return InstrumentType.LOF

        return InstrumentType.ETF  # safe default


__all__ = [
    "Instrument",
    "InstrumentType",
    "Exchange",
    "TradingStatus",
]
