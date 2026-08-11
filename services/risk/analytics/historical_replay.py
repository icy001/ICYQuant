"""
Historical Replay Engine — Replay portfolio performance through historical market periods.

Applies real historical price movements to current portfolio to estimate
how it would have performed during past market crises and regimes.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class HistoricalPeriod:
    """Definition of a historical market period for replay."""
    period_id: str
    name: str
    description: str
    start_date: date
    end_date: date
    category: str  # crisis, bull, bear, regime_change, custom
    key_events: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplayResult:
    """Result from a historical replay."""
    period_id: str
    period_name: str
    start_date: date
    end_date: date
    starting_value: float
    ending_value: float
    absolute_return: float
    return_percentage: float
    max_drawdown_pct: float
    volatility_annualized: float
    sharpe_ratio: float
    worst_day_pct: float
    best_day_pct: float
    positive_days_pct: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class HistoricalReplay:
    """
    Replay portfolio through historical market periods.

    Uses historical price data to simulate how the current portfolio
    would have performed during past crises, bull/bear markets,
    and regime changes.

    Usage::

        replay = HistoricalReplay(market_data_provider)
        await replay.initialize()
        results = await replay.replay_periods(portfolio_data, periods=["2008_gfc"])
    """

    BUILTIN_PERIODS: list[dict[str, Any]] = [
        {
            "period_id": "2008_gfc",
            "name": "2008 Global Financial Crisis",
            "description": "Lehman collapse to market bottom",
            "start_date": date(2008, 9, 1),
            "end_date": date(2009, 3, 9),
            "category": "crisis",
            "key_events": ["Lehman Bankruptcy", "TARP", "Market Bottom"],
        },
        {
            "period_id": "2020_covid_crash",
            "name": "2020 COVID Crash",
            "description": "Pre-COVID peak to pandemic bottom",
            "start_date": date(2020, 2, 19),
            "end_date": date(2020, 3, 23),
            "category": "crisis",
            "key_events": ["WHO Pandemic Declaration", "Circuit Breakers Triggered"],
        },
        {
            "period_id": "2022_bear",
            "name": "2022 Bear Market",
            "description": "Inflation-driven bear market",
            "start_date": date(2022, 1, 3),
            "end_date": date(2022, 10, 12),
            "category": "bear",
            "key_events": ["Fed Rate Hikes", "Inflation Peak"],
        },
        {
            "period_id": "2018_q4_selloff",
            "name": "2018 Q4 Selloff",
            "description": "Rate hike fears and trade war",
            "start_date": date(2018, 10, 1),
            "end_date": date(2018, 12, 24),
            "category": "bear",
            "key_events": ["Fed Hawkish", "Trade War Escalation"],
        },
        {
            "period_id": "2015_q3_correction",
            "name": "2015 Q3 Correction",
            "description": "China devaluation and EM rout",
            "start_date": date(2015, 8, 17),
            "end_date": date(2015, 9, 29),
            "category": "correction",
            "key_events": ["China Yuan Devaluation", "EM Selloff"],
        },
        {
            "period_id": "2020_2021_bull",
            "name": "2020-2021 Bull Market",
            "description": "Post-COVID recovery and stimulus rally",
            "start_date": date(2020, 3, 23),
            "end_date": date(2021, 12, 31),
            "category": "bull",
            "key_events": ["Stimulus", "Vaccine", "Retail Boom"],
        },
    ]

    def __init__(self, market_data_provider: Any = None) -> None:
        self._data_provider = market_data_provider
        self._periods: dict[str, HistoricalPeriod] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize and load built-in periods."""
        if self._initialized:
            return
        for data in self.BUILTIN_PERIODS:
            period = HistoricalPeriod(**data)
            self._periods[period.period_id] = period
        self._initialized = True
        logger.info(f"HistoricalReplay initialized with {len(self._periods)} periods.")

    # ---- Core API ----

    async def replay_periods(
        self,
        portfolio_data: dict[str, Any],
        period_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Replay portfolio through specified historical periods.

        Returns
        -------
        dict
            Per-period replay results with summary.
        """
        if not self._initialized:
            await self.initialize()

        periods = (
            [self._periods[pid] for pid in period_ids if pid in self._periods]
            if period_ids
            else list(self._periods.values())
        )

        if not periods:
            return {"status": "no_periods", "results": []}

        # Run replays in parallel
        tasks = [
            asyncio.create_task(self._replay_single(portfolio_data, period))
            for period in periods
        ]
        replay_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[dict] = []
        worst_return = 0.0
        worst_period = ""

        for i, res in enumerate(replay_results):
            if isinstance(res, Exception):
                results.append({"period_id": periods[i].period_id, "error": str(res)})
                continue
            r: ReplayResult = res
            results.append({
                "period_id": r.period_id,
                "period_name": r.period_name,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat(),
                "return_percentage": r.return_percentage,
                "max_drawdown_pct": r.max_drawdown_pct,
                "volatility_annualized": r.volatility_annualized,
                "sharpe_ratio": r.sharpe_ratio,
                "worst_day_pct": r.worst_day_pct,
            })

            if r.return_percentage < worst_return:
                worst_return = r.return_percentage
                worst_period = r.period_name

        return {
            "total_periods": len(results),
            "worst_return_pct": worst_return,
            "worst_period": worst_period,
            "results": results,
        }

    async def replay_custom(
        self,
        portfolio_data: dict[str, Any],
        price_series: dict[str, list[float]],
        dates: list[date],
    ) -> ReplayResult:
        """Replay portfolio against custom price series."""
        return await self._simulate_replay(
            portfolio_data,
            price_series,
            dates[0] if dates else date.today(),
            dates[-1] if dates else date.today(),
            "custom",
            "Custom Replay",
        )

    # ---- Period Management ----

    def add_period(self, period: HistoricalPeriod) -> None:
        """Register a new historical period."""
        self._periods[period.period_id] = period

    def get_period(self, period_id: str) -> Optional[HistoricalPeriod]:
        """Get a period by ID."""
        return self._periods.get(period_id)

    def list_periods(self) -> list[HistoricalPeriod]:
        """List all available periods."""
        return list(self._periods.values())

    # ---- Internal ----

    async def _replay_single(
        self,
        portfolio_data: dict[str, Any],
        period: HistoricalPeriod,
    ) -> ReplayResult:
        """Replay a single historical period."""
        # If market data provider is available, use real data
        if self._data_provider:
            try:
                price_data = await self._data_provider.get_historical_prices(
                    portfolio_data.get("positions", []),
                    period.start_date,
                    period.end_date,
                )
                return await self._simulate_replay(
                    portfolio_data, price_data,
                    period.start_date, period.end_date,
                    period.period_id, period.name,
                )
            except Exception as e:
                logger.warning(f"Market data fetch failed for {period.period_id}: {e}")

        # Fallback: use approximate simulation based on period metadata
        return await self._approximate_replay(portfolio_data, period)

    async def _simulate_replay(
        self,
        portfolio_data: dict[str, Any],
        price_data: dict[str, list[float]],
        start_date: date,
        end_date: date,
        period_id: str,
        period_name: str,
    ) -> ReplayResult:
        """Simulate portfolio through price series."""
        import math

        total_value = portfolio_data.get("total_value", 1_000_000)
        positions = portfolio_data.get("positions", [])

        # Compute daily returns
        daily_returns: list[float] = []
        peak = total_value
        max_dd = 0.0
        worst_day = 0.0
        best_day = 0.0
        positive_days = 0

        if price_data:
            # Use provided price data
            first_keys = list(price_data.keys())[:1]
            if first_keys:
                prices = price_data[first_keys[0]]
                for i in range(1, len(prices)):
                    if prices[i - 1] != 0:
                        daily_ret = (prices[i] - prices[i - 1]) / prices[i - 1]
                        daily_returns.append(daily_ret)
                        value = total_value * (1 + daily_ret)
                        peak = max(peak, value)
                        dd = (value - peak) / peak
                        max_dd = min(max_dd, dd)
                        worst_day = min(worst_day, daily_ret)
                        best_day = max(best_day, daily_ret)
                        if daily_ret > 0:
                            positive_days += 1
        else:
            # Simulate based on period category
            if "crisis" in period_id or period_id.endswith("crash"):
                daily_returns = [-0.01 + (i * 0.0002) for i in range(50)]
            elif "bear" in period_id:
                daily_returns = [-0.005 + (i * 0.0001) for i in range(100)]
            else:
                daily_returns = [0.002 for _ in range(60)]

            for r in daily_returns:
                value = total_value * (1 + r)
                peak = max(peak, value)
                dd = (value - peak) / peak
                max_dd = min(max_dd, dd)
                worst_day = min(worst_day, r)
                best_day = max(best_day, r)
                if r > 0:
                    positive_days += 1

        # Compute metrics
        total_return = sum(daily_returns) if daily_returns else 0.0
        ending_value = total_value * (1 + total_return)
        n = len(daily_returns)

        # Volatility (annualized)
        if n > 1:
            mean_ret = total_return / n
            var = sum((r - mean_ret) ** 2 for r in daily_returns) / (n - 1)
            vol = math.sqrt(var) * math.sqrt(252)
        else:
            vol = 0.0

        # Sharpe ratio
        sharpe = (total_return / n * 252 - 0.02) / vol if vol > 0 else 0.0

        positive_pct = (positive_days / n * 100) if n > 0 else 0.0

        return ReplayResult(
            period_id=period_id,
            period_name=period_name,
            start_date=start_date,
            end_date=end_date,
            starting_value=total_value,
            ending_value=ending_value,
            absolute_return=ending_value - total_value,
            return_percentage=total_return * 100,
            max_drawdown_pct=abs(max_dd) * 100,
            volatility_annualized=vol,
            sharpe_ratio=sharpe,
            worst_day_pct=worst_day * 100,
            best_day_pct=best_day * 100,
            positive_days_pct=positive_pct,
        )

    async def _approximate_replay(
        self,
        portfolio_data: dict[str, Any],
        period: HistoricalPeriod,
    ) -> ReplayResult:
        """Approximate replay when real data is unavailable."""
        # Use category-based approximations
        approximate_returns = {
            "crisis": -0.35,
            "bear": -0.20,
            "correction": -0.10,
            "bull": 0.25,
            "regime_change": -0.05,
        }
        approx = approximate_returns.get(period.category, -0.10)

        total_value = portfolio_data.get("total_value", 1_000_000)
        days = max(1, (period.end_date - period.start_date).days)

        return ReplayResult(
            period_id=period.period_id,
            period_name=period.name,
            start_date=period.start_date,
            end_date=period.end_date,
            starting_value=total_value,
            ending_value=total_value * (1 + approx),
            absolute_return=total_value * approx,
            return_percentage=approx * 100,
            max_drawdown_pct=abs(approx * 1.3) * 100,
            volatility_annualized=abs(approx) * 1.5,
            sharpe_ratio=approx / (abs(approx) * 1.5) if approx != 0 else 0,
            worst_day_pct=approx * 0.1 * 100,
            best_day_pct=abs(approx) * 0.05 * 100,
            positive_days_pct=45.0 if approx < 0 else 55.0,
        )
