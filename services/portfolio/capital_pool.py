"""
Capital pool.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class CapitalPool:
    total_capital: Decimal
    allocated_capital: Decimal

    def available(self):
        return self.total_capital - self.allocated_capital