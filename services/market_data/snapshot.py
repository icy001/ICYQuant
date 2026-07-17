"""
Unified market snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass

from .instrument import Instrument
from .quote import Quote


@dataclass(frozen=True)
class MarketSnapshot:
    instrument: Instrument
    quote: Quote