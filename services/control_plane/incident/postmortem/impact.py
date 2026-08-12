"""IncidentImpact — structured blast-radius assessment (spec section 10)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class IncidentImpact:

    affected_accounts: int = 0
    affected_orders: int = 0
    affected_positions: int = 0
    rejected_orders: int = 0
    cancelled_orders: int = 0

    estimated_pnl_impact: float = 0.0
    duration_seconds: float = 0.0

    trading_halted: bool = False

    affected_strategies: Optional[List[str]] = None
    affected_services: Optional[List[str]] = None
