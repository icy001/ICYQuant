"""
Market data enums.
"""

from __future__ import annotations

from enum import Enum


class InstrumentType(str, Enum):
    STOCK = "STOCK"
    ETF = "ETF"
    FUTURE = "FUTURE"
    OPTION = "OPTION"
    FX = "FX"
    CRYPTO = "CRYPTO"