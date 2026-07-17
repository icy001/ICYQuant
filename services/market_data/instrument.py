"""
Financial instrument.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import InstrumentType


@dataclass(frozen=True)
class Instrument:
    symbol: str
    exchange: str
    instrument_type: InstrumentType