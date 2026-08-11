"""
Market Capacity — Aggregate market-level capacity estimation.

Considers total market capitalization, breadth, concentration,
and systemic liquidity constraints.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MarketCapacity:
    """Aggregate market capacity assessment."""

    market_id: str = field(default_factory=lambda: f"MC-{uuid.uuid4().hex[:8]}")
    market_name: str = ""

    # Market size
    total_market_cap: float = 0.0
    total_daily_volume: float = 0.0

    # Breadth
    active_symbols: int = 0
    tradable_symbols: int = 0

    # Concentration
    top_10_concentration: float = 0.0      # % of volume in top 10
    hhi_index: float = 0.0                 # Herfindahl-Hirschman Index

    # Systemic
    max_portfolio_pct: float = 0.05        # max % of market cap
    systemic_capacity: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "market_id": self.market_id,
            "market_name": self.market_name,
            "total_market_cap": self.total_market_cap,
            "total_daily_volume": self.total_daily_volume,
            "active_symbols": self.active_symbols,
            "top_10_concentration": self.top_10_concentration,
        }

    def estimate_systemic_capacity(self) -> float:
        """Estimate total market capacity for a single participant."""
        # Typical: 0.1-0.5% of daily volume for a single fund
        self.systemic_capacity = self.total_daily_volume * 0.003
        return self.systemic_capacity
