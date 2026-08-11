"""
Intraday Risk Engine — Continuous intraday risk evaluation.

Monitors portfolio risk throughout the trading day, detecting
intraday drawdowns, volatility spikes, and threshold breaches
in real-time.

Architecture::

    Market Data → Intraday Risk Engine → Risk Assessment → Alerts → Actions
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .portfolio_snapshot import PortfolioSnapshot

logger = logging.getLogger(__name__)


class IntradayRiskLevel(str, Enum):
    """Intraday risk assessment level."""
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class IntradayRiskAssessment:
    """Result of an intraday risk evaluation."""
    assessment_id: str
    account_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    risk_level: IntradayRiskLevel = IntradayRiskLevel.NORMAL
    risk_score: float = 0.0

    # Intraday metrics
    intraday_pnl: float = 0.0
    intraday_pnl_pct: float = 0.0
    intraday_high: float = 0.0
    intraday_low: float = 0.0
    intraday_volatility: float = 0.0
    intraday_drawdown_pct: float = 0.0

    # Trend
    pnl_trend: str = "flat"  # improving, deteriorating, flat
    volatility_trend: str = "stable"  # increasing, decreasing, stable

    # Alerts
    active_alerts: list[dict[str, Any]] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)

    evaluation_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "account_id": self.account_id,
            "timestamp": self.timestamp.isoformat(),
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "intraday_pnl": self.intraday_pnl,
            "intraday_pnl_pct": self.intraday_pnl_pct,
            "intraday_high": self.intraday_high,
            "intraday_low": self.intraday_low,
            "intraday_volatility": self.intraday_volatility,
            "intraday_drawdown_pct": self.intraday_drawdown_pct,
            "pnl_trend": self.pnl_trend,
            "volatility_trend": self.volatility_trend,
            "active_alerts": self.active_alerts,
            "recommended_actions": self.recommended_actions,
            "evaluation_time_ms": self.evaluation_time_ms,
        }


class IntradayRiskEngine:
    """
    Continuous intraday risk evaluation engine.

    Monitors portfolio risk throughout the trading day, detecting
    intraday drawdowns, volatility spikes, PnL trends, and threshold
    breaches in real-time.

    Usage::

        engine = IntradayRiskEngine()
        await engine.initialize()

        assessment = await engine.evaluate("ACC-01", snapshot, intraday_data)
    """

    def __init__(
        self,
        max_intraday_drawdown_pct: float = 5.0,
        max_intraday_pnl_loss_pct: float = 3.0,
        volatility_spike_threshold: float = 2.0,  # x normal
        engine_id: str = "IRE-01",
    ) -> None:
        self._max_intraday_dd = max_intraday_drawdown_pct
        self._max_pnl_loss = max_intraday_pnl_loss_pct
        self._vol_spike_threshold = volatility_spike_threshold
        self.engine_id = engine_id

        self._intraday_data: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._eval_count: int = 0
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the intraday risk engine."""
        self._initialized = True
        logger.info(f"IntradayRiskEngine [{self.engine_id}] initialized.")

    async def stop(self) -> None:
        """Stop the intraday risk engine."""
        self._initialized = False
        logger.info(f"IntradayRiskEngine [{self.engine_id}] stopped.")

    # ---- Core API ----

    async def evaluate(
        self,
        account_id: str,
        snapshot: PortfolioSnapshot,
        intraday_data: Optional[dict[str, Any]] = None,
    ) -> IntradayRiskAssessment:
        """
        Evaluate intraday risk for an account.

        Args:
            account_id: Account identifier.
            snapshot: Current portfolio snapshot.
            intraday_data: Optional intraday metrics:
                - intraday_high, intraday_low
                - open_equity
                - normal_volatility (baseline)
                - pnl_history (list of intraday PnL snapshots)

        Returns IntradayRiskAssessment.
        """
        t_start = time.perf_counter()

        async with self._lock:
            self._eval_count += 1

        idata = intraday_data or {}
        total_equity = snapshot.total_equity or 1.0

        # Intraday PnL
        open_equity = idata.get("open_equity", total_equity)
        intraday_pnl = total_equity - open_equity
        intraday_pnl_pct = (intraday_pnl / open_equity) * 100 if open_equity > 0 else 0.0

        # Intraday high/low
        intraday_high = idata.get("intraday_high", total_equity)
        intraday_low = idata.get("intraday_low", total_equity)

        # Intraday drawdown (from intraday high)
        intraday_dd_pct = (
            ((intraday_high - total_equity) / intraday_high) * 100
            if intraday_high > 0 else 0.0
        )

        # Volatility
        pnl_history = idata.get("pnl_history", [])
        intraday_volatility = self._compute_volatility(pnl_history)
        normal_vol = idata.get("normal_volatility", intraday_volatility or 0.01)

        # Trends
        pnl_trend = self._compute_trend(pnl_history, window=10)
        vol_trend = "stable"  # Would need volatility history

        # Risk scoring
        risk_score = self._compute_intraday_risk_score(
            intraday_dd_pct,
            intraday_pnl_pct,
            intraday_volatility,
            normal_vol,
        )

        # Level
        risk_level = self._determine_level(risk_score)

        # Alerts
        alerts = self._generate_alerts(
            intraday_dd_pct,
            intraday_pnl_pct,
            intraday_volatility,
            normal_vol,
            risk_level,
        )

        # Actions
        actions = self._generate_actions(risk_level, intraday_dd_pct, intraday_pnl_pct)

        evaluation_time_ms = (time.perf_counter() - t_start) * 1000

        assessment = IntradayRiskAssessment(
            assessment_id=f"INTRA-{self._eval_count:06d}",
            account_id=account_id,
            risk_level=risk_level,
            risk_score=risk_score,
            intraday_pnl=intraday_pnl,
            intraday_pnl_pct=intraday_pnl_pct,
            intraday_high=intraday_high,
            intraday_low=intraday_low,
            intraday_volatility=intraday_volatility,
            intraday_drawdown_pct=intraday_dd_pct,
            pnl_trend=pnl_trend,
            volatility_trend=vol_trend,
            active_alerts=alerts,
            recommended_actions=actions,
            evaluation_time_ms=evaluation_time_ms,
        )

        logger.info(
            f"IntradayRiskEngine [{self.engine_id}]: "
            f"{risk_level.value} (score={risk_score:.1f}, "
            f"dd={intraday_dd_pct:.2f}%, pnl={intraday_pnl_pct:.2f}%)"
        )

        return assessment

    async def quick_check(
        self,
        account_id: str,
        current_equity: float,
        intraday_high: float,
        open_equity: float,
    ) -> dict[str, Any]:
        """Fast intraday risk check with minimal data."""
        dd_pct = ((intraday_high - current_equity) / intraday_high) * 100 if intraday_high > 0 else 0
        pnl_pct = ((current_equity - open_equity) / open_equity) * 100 if open_equity > 0 else 0

        risk_score = self._compute_intraday_risk_score(dd_pct, pnl_pct, 0, 0)
        level = self._determine_level(risk_score)

        return {
            "risk_level": level.value,
            "risk_score": risk_score,
            "intraday_drawdown_pct": dd_pct,
            "intraday_pnl_pct": pnl_pct,
        }

    # ---- Internal ----

    def _compute_intraday_risk_score(
        self,
        dd_pct: float,
        pnl_pct: float,
        volatility: float,
        normal_vol: float,
    ) -> float:
        """Compute weighted intraday risk score."""
        score = 0.0

        # Drawdown: 40%
        if dd_pct > self._max_intraday_dd:
            score += 40 * min(dd_pct / self._max_intraday_dd, 2.0)
        elif dd_pct > self._max_intraday_dd * 0.5:
            score += 20 * (dd_pct / self._max_intraday_dd)

        # PnL loss: 35%
        if pnl_pct < -self._max_pnl_loss:
            score += 35 * min(abs(pnl_pct) / self._max_pnl_loss, 2.0)
        elif pnl_pct < 0:
            score += 15 * (abs(pnl_pct) / self._max_pnl_loss)

        # Volatility spike: 25%
        if normal_vol > 0 and volatility > normal_vol * self._vol_spike_threshold:
            score += 25 * min(volatility / (normal_vol * self._vol_spike_threshold), 2.0)

        return min(score, 100.0)

    def _determine_level(self, risk_score: float) -> IntradayRiskLevel:
        """Determine intraday risk level."""
        if risk_score >= 80:
            return IntradayRiskLevel.CRITICAL
        elif risk_score >= 60:
            return IntradayRiskLevel.HIGH
        elif risk_score >= 40:
            return IntradayRiskLevel.ELEVATED
        elif risk_score >= 20:
            return IntradayRiskLevel.CAUTION
        return IntradayRiskLevel.NORMAL

    def _generate_alerts(
        self,
        dd_pct: float,
        pnl_pct: float,
        volatility: float,
        normal_vol: float,
        level: IntradayRiskLevel,
    ) -> list[dict[str, Any]]:
        """Generate intraday alerts."""
        alerts = []

        if dd_pct > self._max_intraday_dd:
            alerts.append({
                "type": "intraday_drawdown",
                "severity": "CRITICAL",
                "message": f"Intraday drawdown {dd_pct:.2f}% exceeds limit {self._max_intraday_dd}%",
            })
        elif dd_pct > self._max_intraday_dd * 0.7:
            alerts.append({
                "type": "intraday_drawdown",
                "severity": "HIGH",
                "message": f"Intraday drawdown {dd_pct:.2f}% approaching limit",
            })

        if pnl_pct < -self._max_pnl_loss:
            alerts.append({
                "type": "intraday_pnl",
                "severity": "HIGH",
                "message": f"Intraday PnL {pnl_pct:.2f}% exceeds loss limit",
            })

        if normal_vol > 0 and volatility > normal_vol * self._vol_spike_threshold:
            alerts.append({
                "type": "volatility_spike",
                "severity": "MEDIUM",
                "message": f"Volatility spike: {volatility:.4f} vs normal {normal_vol:.4f}",
            })

        return alerts

    def _generate_actions(
        self,
        level: IntradayRiskLevel,
        dd_pct: float,
        pnl_pct: float,
    ) -> list[str]:
        """Generate recommended intraday actions."""
        actions = []

        if level == IntradayRiskLevel.CRITICAL:
            actions.append("HALT all new orders immediately")
            actions.append("Review all open positions for emergency reduction")
        elif level == IntradayRiskLevel.HIGH:
            actions.append("Reduce position sizes by 50%")
            actions.append("Stop adding new positions")
        elif level == IntradayRiskLevel.ELEVATED:
            actions.append("Monitor positions closely")
            actions.append("Consider reducing exposure")

        if dd_pct > self._max_intraday_dd:
            actions.append("Intraday drawdown limit breached — consider stop-loss")

        return actions

    def _compute_volatility(self, pnl_history: list[float]) -> float:
        """Compute volatility from PnL history."""
        if len(pnl_history) < 2:
            return 0.0

        mean = sum(pnl_history) / len(pnl_history)
        variance = sum((x - mean) ** 2 for x in pnl_history) / len(pnl_history)
        return variance ** 0.5

    def _compute_trend(self, history: list[float], window: int = 10) -> str:
        """Compute trend direction from history."""
        if len(history) < 2:
            return "flat"

        recent = history[-window:] if len(history) >= window else history
        if len(recent) < 2:
            return "flat"

        first_half = sum(recent[:len(recent) // 2]) / max(len(recent) // 2, 1)
        second_half = sum(recent[len(recent) // 2:]) / max(len(recent) - len(recent) // 2, 1)

        if second_half > first_half * 1.02:
            return "improving"
        elif second_half < first_half * 0.98:
            return "deteriorating"
        return "flat"

    # ---- Stats ----

    async def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        return {
            "engine_id": self.engine_id,
            "evaluation_count": self._eval_count,
            "initialized": self._initialized,
        }

    async def health_check(self) -> dict[str, Any]:
        """Check engine health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "evaluation_count": self._eval_count,
        }
