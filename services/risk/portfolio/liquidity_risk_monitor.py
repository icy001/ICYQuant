"""
Liquidity Risk Monitor — Portfolio liquidity risk assessment.

Evaluates portfolio liquidity by comparing holding sizes against
market liquidity, estimating exit times, and computing liquidity
scores for each position and the portfolio as a whole.

Architecture::

    Holding Size → Market Liquidity → Exit Time → Liquidity Score
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class LiquidityInfo:
    """Liquidity assessment for a single position."""
    symbol: str
    market_value: float = 0.0
    avg_daily_volume: float = 0.0
    volume_pct: float = 0.0  # position as % of daily volume
    estimated_exit_days: float = 0.0
    estimated_exit_hours: float = 0.0
    bid_ask_spread_pct: float = 0.0
    liquidity_score: float = 100.0  # 0=illiquid, 100=very liquid
    status: str = "LIQUID"


@dataclass
class PortfolioLiquidityReport:
    """Liquidity risk report for the entire portfolio."""
    account_id: str
    positions: dict[str, LiquidityInfo] = field(default_factory=dict)
    portfolio_liquidity_score: float = 100.0
    avg_exit_hours: float = 0.0
    worst_exit_hours: float = 0.0
    worst_symbol: str = ""
    illiquid_positions: int = 0
    total_illiquid_value: float = 0.0
    illiquid_pct: float = 0.0
    liquidity_risk_score: float = 0.0
    risk_level: str = "LOW"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "portfolio_liquidity_score": self.portfolio_liquidity_score,
            "avg_exit_hours": self.avg_exit_hours,
            "worst_exit_hours": self.worst_exit_hours,
            "worst_symbol": self.worst_symbol,
            "illiquid_positions": self.illiquid_positions,
            "total_illiquid_value": self.total_illiquid_value,
            "illiquid_pct": self.illiquid_pct,
            "liquidity_risk_score": self.liquidity_risk_score,
            "risk_level": self.risk_level,
        }


class LiquidityRiskMonitor:
    """
    Portfolio liquidity risk assessment engine.

    Evaluates how easily positions can be exited without significant
    market impact. Uses volume-based analysis, bid-ask spread
    assessment, and concentration-adjusted liquidity scoring.

    Usage::

        monitor = LiquidityRiskMonitor()
        await monitor.initialize()

        report = await monitor.assess("ACC-01", positions, market_data)
    """

    def __init__(
        self,
        max_volume_pct: float = 10.0,
        max_exit_days: float = 5.0,
        max_bid_ask_spread_pct: float = 2.0,
        liquidity_threshold: float = 30.0,
    ) -> None:
        self._max_volume_pct = max_volume_pct
        self._max_exit_days = max_exit_days
        self._max_spread_pct = max_bid_ask_spread_pct
        self._liquidity_threshold = liquidity_threshold
        self._lock = asyncio.Lock()
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the liquidity monitor."""
        self._initialized = True
        logger.info("LiquidityRiskMonitor initialized.")

    async def stop(self) -> None:
        """Stop the liquidity monitor."""
        self._initialized = False
        logger.info("LiquidityRiskMonitor stopped.")

    # ---- Core API ----

    async def assess(
        self,
        account_id: str,
        positions: dict[str, dict[str, Any]],
        market_data: dict[str, dict[str, Any]],
        total_equity: float,
    ) -> PortfolioLiquidityReport:
        """
        Assess liquidity risk for a portfolio.

        Args:
            account_id: Account identifier.
            positions: Dict of symbol → {market_value, quantity, ...}
            market_data: Dict of symbol → {avg_daily_volume, bid, ask, ...}
            total_equity: Total portfolio equity.

        Returns PortfolioLiquidityReport.
        """
        position_liquidity: dict[str, LiquidityInfo] = {}
        total_illiquid_value = 0.0
        total_exit_hours = 0.0
        worst_exit_hours = 0.0
        worst_symbol = ""

        for symbol, pos in positions.items():
            mv = pos.get("market_value", 0)
            mkt = market_data.get(symbol, {})

            avg_volume = mkt.get("avg_daily_volume", 1.0)
            volume_pct = (abs(mv) / avg_volume * 100) if avg_volume > 0 else 100.0

            # Estimated exit: assume can trade 20% of daily volume without impact
            safe_daily_volume = avg_volume * 0.2
            exit_days = (abs(mv) / safe_daily_volume) if safe_daily_volume > 0 else 999
            exit_hours = exit_days * 6.5  # Trading hours per day

            # Bid-ask spread
            bid = mkt.get("bid", 0)
            ask = mkt.get("ask", 0)
            spread_pct = ((ask - bid) / ask * 100) if ask > 0 and bid > 0 else 0.0

            # Liquidity score (0-100)
            score = self._compute_liquidity_score(volume_pct, spread_pct, exit_days)

            status = "LIQUID"
            if score < self._liquidity_threshold:
                status = "ILLIQUID"
                total_illiquid_value += abs(mv)
            elif score < self._liquidity_threshold * 1.5:
                status = "LOW_LIQUIDITY"

            info = LiquidityInfo(
                symbol=symbol,
                market_value=mv,
                avg_daily_volume=avg_volume,
                volume_pct=volume_pct,
                estimated_exit_days=exit_days,
                estimated_exit_hours=exit_hours,
                bid_ask_spread_pct=spread_pct,
                liquidity_score=score,
                status=status,
            )
            position_liquidity[symbol] = info
            total_exit_hours += exit_hours

            if exit_hours > worst_exit_hours:
                worst_exit_hours = exit_hours
                worst_symbol = symbol

        num_positions = len(position_liquidity) or 1
        avg_exit_hours = total_exit_hours / num_positions
        illiquid_pct = (total_illiquid_value / total_equity * 100) if total_equity > 0 else 0.0

        # Portfolio liquidity score: weighted average
        portfolio_score = 0.0
        total_weight = 0.0
        for info in position_liquidity.values():
            weight = abs(info.market_value)
            portfolio_score += info.liquidity_score * weight
            total_weight += weight
        if total_weight > 0:
            portfolio_score /= total_weight
        else:
            portfolio_score = 100.0

        # Risk score
        risk_score = 100.0 - portfolio_score
        risk_level = "LOW"
        if risk_score >= 70:
            risk_level = "CRITICAL"
        elif risk_score >= 50:
            risk_level = "HIGH"
        elif risk_score >= 30:
            risk_level = "MEDIUM"

        return PortfolioLiquidityReport(
            account_id=account_id,
            positions=position_liquidity,
            portfolio_liquidity_score=portfolio_score,
            avg_exit_hours=avg_exit_hours,
            worst_exit_hours=worst_exit_hours,
            worst_symbol=worst_symbol,
            illiquid_positions=sum(1 for i in position_liquidity.values() if i.status == "ILLIQUID"),
            total_illiquid_value=total_illiquid_value,
            illiquid_pct=illiquid_pct,
            liquidity_risk_score=risk_score,
            risk_level=risk_level,
        )

    async def check_symbol_liquidity(
        self,
        symbol: str,
        market_value: float,
        avg_daily_volume: float,
    ) -> LiquidityInfo:
        """Quick liquidity check for a single symbol."""
        mkt = {"avg_daily_volume": avg_daily_volume, "bid": 0, "ask": 0}
        report = await self.assess(
            account_id="CHECK",
            positions={symbol: {"market_value": market_value}},
            market_data={symbol: mkt},
            total_equity=abs(market_value),
        )
        return report.positions.get(symbol, LiquidityInfo(symbol=symbol))

    # ---- Internal ----

    def _compute_liquidity_score(
        self,
        volume_pct: float,
        spread_pct: float,
        exit_days: float,
    ) -> float:
        """Compute liquidity score (0-100) for a position."""
        score = 100.0

        # Volume penalty
        if volume_pct > self._max_volume_pct:
            score -= 40 * min(volume_pct / self._max_volume_pct, 2.0)
        elif volume_pct > self._max_volume_pct * 0.5:
            score -= 20 * (volume_pct / self._max_volume_pct)

        # Spread penalty
        if spread_pct > self._max_spread_pct:
            score -= 30 * min(spread_pct / self._max_spread_pct, 2.0)

        # Exit time penalty
        if exit_days > self._max_exit_days:
            score -= 30 * min(exit_days / self._max_exit_days, 2.0)
        elif exit_days > 1:
            score -= 15 * (exit_days / self._max_exit_days)

        return max(score, 0.0)

    # ---- Stats ----

    async def get_stats(self) -> dict[str, Any]:
        """Get monitor statistics."""
        return {
            "max_volume_pct": self._max_volume_pct,
            "max_exit_days": self._max_exit_days,
            "max_spread_pct": self._max_spread_pct,
            "liquidity_threshold": self._liquidity_threshold,
        }

    async def health_check(self) -> dict[str, Any]:
        """Check monitor health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
        }
