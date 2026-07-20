"""
Portfolio equity snapshot.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class EquitySnapshot:
    timestamp: str
    nav: Decimal