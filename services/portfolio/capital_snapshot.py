"""
Capital snapshot.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CapitalSnapshot:
    total: Decimal
    allocated: Decimal
    available: Decimal