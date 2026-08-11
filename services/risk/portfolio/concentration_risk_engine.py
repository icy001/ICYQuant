"""
Concentration Risk Engine — Portfolio concentration risk analysis.

Monitors single-name concentration, sector concentration, and
asset class concentration with configurable limits. Detects
over-concentration and generates risk warnings.

Architecture::

    Positions → Single-Name Concentration → Sector → Asset Class → Risk Score
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConcentrationMetrics:
    """Concentration risk metrics for a portfolio."""
    account_id: str
    total_equity: float = 0.0

    # Single-name concentration
    top_holding_pct: float = 0.0
    top_holding_symbol: str = ""
    top_3_holdings_pct: float = 0.0
    top_5_holdings_pct: float = 0.0
    herfindahl_index: float = 0.0  # HHI measure of concentration

    # Sector concentration
    sector_concentration: dict[str, float] = field(default_factory=dict)
    max_sector_pct: float = 0.0
    max_sector_name: str = ""

    # Asset class concentration
    asset_class_concentration: dict[str, float] = field(default_factory=dict)

    # Risk assessment
    concentration_risk_score: float = 0.0
    risk_level: str = "LOW"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "total_equity": self.total_equity,
            "top_holding_pct": self.top_holding_pct,
            "top_holding_symbol": self.top_holding_symbol,
            "top_3_holdings_pct": self.top_3_holdings_pct,
            "top_5_holdings_pct": self.top_5_holdings_pct,
            "herfindahl_index": self.herfindahl_index,
            "sector_concentration": dict(self.sector_concentration),
            "max_sector_pct": self.max_sector_pct,
            "max_sector_name": self.max_sector_name,
            "asset_class_concentration": dict(self.asset_class_concentration),
            "concentration_risk_score": self.concentration_risk_score,
            "risk_level": self.risk_level,
        }


class ConcentrationRiskEngine:
    """
    Portfolio concentration risk analysis engine.

    Monitors single-name, sector, and asset class concentration
    with configurable limits. Computes Herfindahl-Hirschman Index
    (HHI) for overall portfolio concentration.

    Usage::

        engine = ConcentrationRiskEngine()
        await engine.initialize()

        metrics = await engine.analyze("ACC-01", positions, total_equity)
    """

    def __init__(
        self,
        max_single_pct: float = 15.0,
        max_sector_pct: float = 40.0,
        max_asset_class_pct: float = 80.0,
        max_top3_pct: float = 35.0,
        max_top5_pct: float = 50.0,
    ) -> None:
        self._max_single_pct = max_single_pct
        self._max_sector_pct = max_sector_pct
        self._max_asset_class_pct = max_asset_class_pct
        self._max_top3_pct = max_top3_pct
        self._max_top5_pct = max_top5_pct
        self._lock = asyncio.Lock()
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the concentration risk engine."""
        self._initialized = True
        logger.info("ConcentrationRiskEngine initialized.")

    async def stop(self) -> None:
        """Stop the concentration risk engine."""
        self._initialized = False
        logger.info("ConcentrationRiskEngine stopped.")

    # ---- Core API ----

    async def analyze(
        self,
        account_id: str,
        positions: dict[str, dict[str, Any]],
        total_equity: float,
    ) -> ConcentrationMetrics:
        """
        Analyze concentration risk for a set of positions.

        Args:
            account_id: Account identifier.
            positions: Dict of symbol → {market_value, sector, asset_class, ...}
            total_equity: Total portfolio equity.

        Returns ConcentrationMetrics with full analysis.
        """
        if total_equity <= 0:
            return ConcentrationMetrics(account_id=account_id)

        # Compute weights
        weights: dict[str, float] = {}
        sector_weights: dict[str, float] = {}
        asset_class_weights: dict[str, float] = {}

        for symbol, pos in positions.items():
            mv = pos.get("market_value", 0)
            weight = (mv / total_equity) * 100
            weights[symbol] = weight

            sector = pos.get("sector", "Other")
            sector_weights[sector] = sector_weights.get(sector, 0.0) + weight

            asset_class = pos.get("asset_class", "EQUITY")
            asset_class_weights[asset_class] = asset_class_weights.get(asset_class, 0.0) + weight

        # Top holdings
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        top_holding_symbol = sorted_weights[0][0] if sorted_weights else ""
        top_holding_pct = sorted_weights[0][1] if sorted_weights else 0.0
        top_3_pct = sum(w for _, w in sorted_weights[:3])
        top_5_pct = sum(w for _, w in sorted_weights[:5])

        # HHI (0-10000 scale)
        hhi = sum(w * w for w in weights.values())

        # Max sector
        max_sector = max(sector_weights.items(), key=lambda x: x[1]) if sector_weights else ("", 0.0)

        # Compute risk score
        risk_score = self._compute_risk_score(
            top_holding_pct, top_3_pct, top_5_pct, hhi,
            max_sector[1], max(asset_class_weights.values()) if asset_class_weights else 0.0
        )

        risk_level = "LOW"
        if risk_score >= 80:
            risk_level = "CRITICAL"
        elif risk_score >= 60:
            risk_level = "HIGH"
        elif risk_score >= 30:
            risk_level = "MEDIUM"

        return ConcentrationMetrics(
            account_id=account_id,
            total_equity=total_equity,
            top_holding_pct=top_holding_pct,
            top_holding_symbol=top_holding_symbol,
            top_3_holdings_pct=top_3_pct,
            top_5_holdings_pct=top_5_pct,
            herfindahl_index=hhi,
            sector_concentration=dict(sector_weights),
            max_sector_pct=max_sector[1],
            max_sector_name=max_sector[0],
            asset_class_concentration=dict(asset_class_weights),
            concentration_risk_score=risk_score,
            risk_level=risk_level,
        )

    async def check_limit(
        self,
        symbol: str,
        proposed_value: float,
        total_equity: float,
        current_positions: dict[str, float],
    ) -> dict[str, Any]:
        """
        Check if a proposed position would breach concentration limits.

        Returns {passed: bool, message: str, current_pct: float, proposed_pct: float}.
        """
        if total_equity <= 0:
            return {"passed": False, "message": "Invalid equity"}

        current_mv = current_positions.get(symbol, 0.0)
        current_pct = (current_mv / total_equity) * 100
        proposed_pct = ((current_mv + proposed_value) / total_equity) * 100

        if proposed_pct > self._max_single_pct:
            return {
                "passed": False,
                "message": f"{symbol} would be {proposed_pct:.1f}% (limit: {self._max_single_pct:.1f}%)",
                "current_pct": current_pct,
                "proposed_pct": proposed_pct,
                "limit": self._max_single_pct,
            }

        return {
            "passed": True,
            "message": f"{symbol} concentration OK ({proposed_pct:.1f}%)",
            "current_pct": current_pct,
            "proposed_pct": proposed_pct,
            "limit": self._max_single_pct,
        }

    # ---- Internal ----

    def _compute_risk_score(
        self,
        top_pct: float,
        top3_pct: float,
        top5_pct: float,
        hhi: float,
        max_sector_pct: float,
        max_asset_pct: float,
    ) -> float:
        """Compute weighted concentration risk score."""
        score = 0.0

        # Single-name: 35% weight
        if top_pct > self._max_single_pct:
            score += 35 * min((top_pct / self._max_single_pct), 2.0)
        elif top_pct > self._max_single_pct * 0.7:
            score += 15

        # Top 3: 15% weight
        if top3_pct > self._max_top3_pct:
            score += 15 * min((top3_pct / self._max_top3_pct), 2.0)

        # Top 5: 10% weight
        if top5_pct > self._max_top5_pct:
            score += 10 * min((top5_pct / self._max_top5_pct), 2.0)

        # HHI: 20% weight
        if hhi > 2500:  # Highly concentrated
            score += 20
        elif hhi > 1500:  # Moderately concentrated
            score += 10

        # Sector: 10% weight
        if max_sector_pct > self._max_sector_pct:
            score += 10 * min((max_sector_pct / self._max_sector_pct), 2.0)

        # Asset class: 10% weight
        if max_asset_pct > self._max_asset_class_pct:
            score += 10 * min((max_asset_pct / self._max_asset_class_pct), 2.0)

        return min(score, 100.0)

    # ---- Stats ----

    async def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        return {
            "max_single_pct": self._max_single_pct,
            "max_sector_pct": self._max_sector_pct,
            "max_asset_class_pct": self._max_asset_class_pct,
        }

    async def health_check(self) -> dict[str, Any]:
        """Check engine health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
        }
