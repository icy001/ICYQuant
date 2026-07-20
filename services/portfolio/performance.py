"""
Performance attribution model.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PerformanceContribution:
    entity_id: str
    pnl: Decimal
    contribution: Decimal