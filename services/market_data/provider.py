"""
Market data provider definitions.
"""

from __future__ import annotations

from enum import Enum


class MarketProvider(str, Enum):
    BINANCE = "BINANCE"
    IBKR = "IBKR"
    CTP = "CTP"
    POLYGON = "POLYGON"
    MOCK = "MOCK"