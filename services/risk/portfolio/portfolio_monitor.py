"""
Portfolio Monitor — Continuous portfolio-wide risk monitoring.

Runs periodic evaluations of the full portfolio against configured
risk limits and generates aggregated risk assessments.

Architecture::

    Portfolio Snapshot → Monitor Evaluation → Risk Assessment → Alerts
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .portfolio_snapshot import PortfolioSnapshot

logger = logging.getLogger(__name__)


class MonitorStatus(str, Enum):
    """Portfolio monitor operational status."""
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


class PortfolioRiskLevel(str, Enum):
    """Portfolio-wide risk assessment level."""
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class MonitorConfig:
    """Portfolio monitor configuration."""
    evaluation_interval_seconds: float = 1.0
    max_risk_score: float = 70.0
    max_drawdown_pct: float = 20.0
    max_leverage_ratio: float = 3.0
    max_concentration_pct: float = 30.0
    max_gross_exposure_pct: float = 200.0
    min_liquidity_score: float = 30.0
    enable_greeks_monitoring: bool = True
    enable_factor_monitoring: bool = True
    enable_correlation_monitoring: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitorResult:
    """Result of a single portfolio monitor evaluation."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    risk_level: PortfolioRiskLevel = PortfolioRiskLevel.NORMAL
    risk_score: float = 0.0
    snapshot: Optional[PortfolioSnapshot] = None
    breaches: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    evaluation_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class PortfolioMonitor:
    """
    Continuous portfolio-wide risk monitoring engine.

    Periodically evaluates the full portfolio against configured
    risk limits and generates aggregated risk assessments. Triggers
    alerts when thresholds are breached.

    Usage::

        monitor = PortfolioMonitor(config=MonitorConfig())
        await monitor.start()
        result = await monitor.evaluate(snapshot)
    """

    def __init__(self, config: Optional[MonitorConfig] = None) -> None:
        self._config = config or MonitorConfig()
        self._status = MonitorStatus.STOPPED
        self._latest_result: Optional[MonitorResult] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._eval_count: int = 0
        self._breach_count: int = 0

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the portfolio monitor."""
        logger.info("PortfolioMonitor initializing...")
        logger.info("PortfolioMonitor initialized.")

    async def start(self) -> None:
        """Start continuous monitoring."""
        self._status = MonitorStatus.RUNNING
        logger.info("PortfolioMonitor started.")

    async def stop(self) -> None:
        """Stop monitoring."""
        self._status = MonitorStatus.STOPPED
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("PortfolioMonitor stopped.")

    async def pause(self) -> None:
        """Pause monitoring."""
        self._status = MonitorStatus.PAUSED
        logger.info("PortfolioMonitor paused.")

    async def resume(self) -> None:
        """Resume monitoring."""
        self._status = MonitorStatus.RUNNING
        logger.info("PortfolioMonitor resumed.")

    # ---- Core API ----

    async def evaluate(self, snapshot: PortfolioSnapshot) -> MonitorResult:
        """
        Evaluate a portfolio snapshot against all risk limits.

        Returns a MonitorResult with risk level, score, and any breaches.
        """
        if self._status != MonitorStatus.RUNNING:
            logger.warning("PortfolioMonitor not running; evaluating anyway.")

        import time
        t_start = time.perf_counter()

        async with self._lock:
            self._eval_count += 1

        breaches: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        risk_score = 0.0

        # ---- Drawdown Check ----
        if snapshot.current_drawdown_pct > self._config.max_drawdown_pct:
            breaches.append({
                "type": "drawdown",
                "current": snapshot.current_drawdown_pct,
                "limit": self._config.max_drawdown_pct,
                "message": f"Drawdown {snapshot.current_drawdown_pct:.1f}% exceeds limit {self._config.max_drawdown_pct:.1f}%",
            })
            risk_score += 30
        elif snapshot.current_drawdown_pct > self._config.max_drawdown_pct * 0.7:
            warnings.append({
                "type": "drawdown",
                "current": snapshot.current_drawdown_pct,
                "limit": self._config.max_drawdown_pct,
                "message": f"Drawdown {snapshot.current_drawdown_pct:.1f}% approaching limit",
            })
            risk_score += 15

        # ---- Leverage Check ----
        if snapshot.leverage_ratio > self._config.max_leverage_ratio:
            breaches.append({
                "type": "leverage",
                "current": snapshot.leverage_ratio,
                "limit": self._config.max_leverage_ratio,
                "message": f"Leverage {snapshot.leverage_ratio:.2f}x exceeds limit {self._config.max_leverage_ratio:.2f}x",
            })
            risk_score += 25
        elif snapshot.leverage_ratio > self._config.max_leverage_ratio * 0.8:
            warnings.append({
                "type": "leverage",
                "current": snapshot.leverage_ratio,
                "limit": self._config.max_leverage_ratio,
                "message": f"Leverage {snapshot.leverage_ratio:.2f}x approaching limit",
            })
            risk_score += 10

        # ---- Concentration Check ----
        if snapshot.top_holding_pct > self._config.max_concentration_pct:
            breaches.append({
                "type": "concentration",
                "current": snapshot.top_holding_pct,
                "limit": self._config.max_concentration_pct,
                "message": f"Top holding {snapshot.top_holding_pct:.1f}% exceeds limit {self._config.max_concentration_pct:.1f}%",
            })
            risk_score += 20
        elif snapshot.top_holding_pct > self._config.max_concentration_pct * 0.8:
            warnings.append({
                "type": "concentration",
                "current": snapshot.top_holding_pct,
                "limit": self._config.max_concentration_pct,
                "message": f"Top holding {snapshot.top_holding_pct:.1f}% approaching limit",
            })
            risk_score += 10

        # ---- Gross Exposure Check ----
        if snapshot.total_equity > 0:
            gross_pct = (snapshot.gross_exposure / snapshot.total_equity) * 100
            if gross_pct > self._config.max_gross_exposure_pct:
                breaches.append({
                    "type": "gross_exposure",
                    "current": gross_pct,
                    "limit": self._config.max_gross_exposure_pct,
                    "message": f"Gross exposure {gross_pct:.1f}% exceeds limit",
                })
                risk_score += 20

        # ---- Liquidity Check ----
        if snapshot.portfolio_liquidity_score < self._config.min_liquidity_score:
            breaches.append({
                "type": "liquidity",
                "current": snapshot.portfolio_liquidity_score,
                "limit": self._config.min_liquidity_score,
                "message": f"Liquidity score {snapshot.portfolio_liquidity_score:.1f} below minimum {self._config.min_liquidity_score:.1f}",
            })
            risk_score += 20
        elif snapshot.portfolio_liquidity_score < self._config.min_liquidity_score * 1.5:
            warnings.append({
                "type": "liquidity",
                "current": snapshot.portfolio_liquidity_score,
                "limit": self._config.min_liquidity_score,
                "message": f"Liquidity score {snapshot.portfolio_liquidity_score:.1f} is low",
            })
            risk_score += 10

        # ---- Margin Check ----
        if snapshot.margin_ratio > 0.9:
            breaches.append({
                "type": "margin",
                "current": snapshot.margin_ratio,
                "limit": 0.9,
                "message": f"Margin usage {snapshot.margin_ratio:.1%} critical",
            })
            risk_score += 30
        elif snapshot.margin_ratio > 0.7:
            warnings.append({
                "type": "margin",
                "current": snapshot.margin_ratio,
                "limit": 0.7,
                "message": f"Margin usage {snapshot.margin_ratio:.1%} elevated",
            })
            risk_score += 15

        risk_score = min(risk_score, 100.0)

        # Determine risk level
        if risk_score >= 80:
            risk_level = PortfolioRiskLevel.CRITICAL
        elif risk_score >= 60:
            risk_level = PortfolioRiskLevel.HIGH
        elif risk_score >= 30:
            risk_level = PortfolioRiskLevel.ELEVATED
        else:
            risk_level = PortfolioRiskLevel.NORMAL

        evaluation_time_ms = (time.perf_counter() - t_start) * 1000

        result = MonitorResult(
            risk_level=risk_level,
            risk_score=risk_score,
            snapshot=snapshot,
            breaches=breaches,
            warnings=warnings,
            evaluation_time_ms=evaluation_time_ms,
        )

        if breaches:
            async with self._lock:
                self._breach_count += 1

        self._latest_result = result
        logger.info(
            f"Portfolio evaluation: {risk_level.value} (score={risk_score:.1f}, "
            f"breaches={len(breaches)}, warnings={len(warnings)}, "
            f"time={evaluation_time_ms:.1f}ms)"
        )

        return result

    # ---- Query ----

    def get_latest_result(self) -> Optional[MonitorResult]:
        """Get the most recent evaluation result."""
        return self._latest_result

    async def get_stats(self) -> dict[str, Any]:
        """Get monitor statistics."""
        async with self._lock:
            return {
                "status": self._status.value,
                "evaluation_count": self._eval_count,
                "breach_count": self._breach_count,
                "latest_risk_level": (
                    self._latest_result.risk_level.value
                    if self._latest_result else "N/A"
                ),
                "latest_risk_score": (
                    self._latest_result.risk_score
                    if self._latest_result else 0.0
                ),
            }

    async def health_check(self) -> dict[str, Any]:
        """Check monitor health."""
        return {
            "status": self._status.value,
            "evaluation_count": self._eval_count,
            "breach_count": self._breach_count,
        }
