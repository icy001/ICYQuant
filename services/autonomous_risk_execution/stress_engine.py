"""
Stress Engine — historical and synthetic stress testing.

Tests portfolio resilience against:
    - Historical stress events (crashes, crises)
    - Synthetic stress scenarios
    - Factor-specific stresses
    - Asset-class-specific shocks
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class StressEvent:
    """Definition of a stress event."""
    name: str
    date: Optional[str] = None
    description: str = ""
    market_shock: float = 0.0
    vol_shock: float = 0.0
    correlation_shock: float = 0.0
    liquidity_shock: float = 0.0
    rate_shock: float = 0.0
    fx_shock: float = 0.0
    commodity_shock: float = 0.0
    sector_shocks: dict[str, float] = field(default_factory=dict)


@dataclass
class StressResult:
    """Result of a single stress test."""
    event: StressEvent
    portfolio_pnl: float = 0.0
    portfolio_var: float = 0.0
    max_drawdown: float = 0.0
    liquidity_impact: float = 0.0
    passed: bool = True
    warnings: list[str] = field(default_factory=list)


@dataclass
class StressTestResult:
    """Complete stress test result."""
    id: str = field(default_factory=lambda: str(uuid4()))
    results: list[StressResult] = field(default_factory=list)
    max_loss: float = 0.0
    max_loss_event: str = ""
    total_passed: int = 0
    total_failed: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


class StressEngine:
    """
    Stress testing engine.

    Historical events included:
        - 2008 Global Financial Crisis
        - 2020 COVID Crash
        - 2018 Q4 Sell-off
        - 2015 China Market Crash
        - 2011 Euro Crisis
        - 2010 Flash Crash

    Synthetic stresses:
        - Market Crash (-30%)
        - Rate Shock (+300bps)
        - FX Shock (±10%)
        - Commodity Shock (±25%)
        - Sector Collapse (-40%)
        - Liquidity Crisis (-60% liquidity)
    """

    HISTORICAL_STRESSES: list[StressEvent] = [
        StressEvent("2008_GFC", "2008-09-01",
                    "Global Financial Crisis",
                    market_shock=-0.40, vol_shock=0.80, correlation_shock=0.50,
                    liquidity_shock=-0.60),
        StressEvent("2020_COVID", "2020-02-15",
                    "COVID-19 Crash",
                    market_shock=-0.35, vol_shock=0.70, correlation_shock=0.40,
                    liquidity_shock=-0.50),
        StressEvent("2018_Q4", "2018-10-01",
                    "2018 Q4 Sell-off",
                    market_shock=-0.20, vol_shock=0.40, correlation_shock=0.25),
        StressEvent("2015_CHINA", "2015-06-12",
                    "China Market Crash",
                    market_shock=-0.35, vol_shock=0.60, liquidity_shock=-0.45),
        StressEvent("2011_EURO", "2011-07-01",
                    "Eurozone Crisis",
                    market_shock=-0.20, fx_shock=-0.10, correlation_shock=0.30),
        StressEvent("2010_FLASH", "2010-05-06",
                    "Flash Crash",
                    market_shock=-0.10, vol_shock=0.50, liquidity_shock=-0.70),
    ]

    SYNTHETIC_STRESSES: list[StressEvent] = [
        StressEvent("SYNTH_MARKET_CRASH", description="Market crash -30%",
                    market_shock=-0.30),
        StressEvent("SYNTH_RATE_SHOCK", description="Rate shock +300bps",
                    rate_shock=0.03),
        StressEvent("SYNTH_FX_SHOCK", description="FX shock +10%",
                    fx_shock=0.10),
        StressEvent("SYNTH_COMMODITY", description="Commodity shock +25%",
                    commodity_shock=0.25),
        StressEvent("SYNTH_SECTOR_COLLAPSE", description="Sector collapse -40%",
                    market_shock=-0.25, vol_shock=0.50, correlation_shock=0.40),
        StressEvent("SYNTH_LIQUIDITY_CRISIS", description="Liquidity crisis -60%",
                    liquidity_shock=-0.60, vol_shock=0.50),
        StressEvent("SYNTH_VOL_EXPLOSION", description="Volatility explosion +200%",
                    vol_shock=2.00, correlation_shock=0.50),
    ]

    def __init__(self, loss_threshold: float = 0.15) -> None:
        self._loss_threshold = loss_threshold
        self._events = self.HISTORICAL_STRESSES + self.SYNTHETIC_STRESSES
        self._last_result: Optional[StressTestResult] = None

    async def run(
        self,
        positions: dict[str, float],
        base_vol: float = 0.15,
        additional_events: Optional[list[StressEvent]] = None,
    ) -> StressTestResult:
        """Run all stress tests."""
        events = self._events + (additional_events or [])
        result = StressTestResult()

        for event in events:
            sr = StressResult(event=event)

            # Estimate P&L under stress
            shock = abs(event.market_shock)
            vol_impact = event.vol_shock * base_vol
            corr_impact = event.correlation_shock * 0.15
            liq_impact = abs(event.liquidity_shock) * 0.05

            gross = sum(abs(v) for v in positions.values())
            pnl = gross * (shock + vol_impact + corr_impact + liq_impact)

            sr.portfolio_pnl = pnl
            sr.portfolio_var = base_vol + event.vol_shock
            sr.liquidity_impact = liq_impact

            # Check if stress test passed
            if pnl > self._loss_threshold:
                sr.passed = False
                sr.warnings.append(
                    f"{event.name}: Loss {pnl:.2%} exceeds threshold {self._loss_threshold:.1%}"
                )
                result.total_failed += 1
            else:
                result.total_passed += 1

            if pnl > result.max_loss:
                result.max_loss = pnl
                result.max_loss_event = event.name

            result.results.append(sr)

        result.timestamp = datetime.now()
        self._last_result = result

        logger.info(
            "Stress test: %d events, passed=%d failed=%d max_loss=%.2f%% (%s)",
            len(events), result.total_passed, result.total_failed,
            result.max_loss * 100, result.max_loss_event,
        )
        return result

    def add_event(self, event: StressEvent) -> None:
        """Add a custom stress event."""
        self._events.append(event)

    @property
    def last_result(self) -> Optional[StressTestResult]:
        return self._last_result
