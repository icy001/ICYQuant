"""
Capital allocation model.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class CapitalAllocation:
    strategy_id: str
    allocated_capital: Decimal
    reserved_capital: Decimal