"""
Portfolio Risk Engine — Unified portfolio-wide risk evaluation.

Aggregates data from all portfolio monitors (exposure, PnL, margin,
drawdown, concentration, greeks, factor, correlation, liquidity)
and produces a comprehensive portfolio risk assessment.

Architecture::

    Portfolio Snapshot
        │
        ├── Exposure Engine ──→ Gross/Net/Long/Short Exposure
        ├── PnL Engine ──→ Realized/Unrealized PnL
        ├── Margin Monitor ──→ Margin Usage
        ├── Drawdown Monitor ──→ Drawdown Metrics
        ├── Concentration Engine ──→ Concentration Risk
        ├── Greeks Engine ──→ Portfolio Greeks
        ├── Factor Engine ──→ Factor Exposures
        ├── Correlation Monitor ──→ Correlation Matrix
        ├── Liquidity Monitor ──→ Liquidity Score
        └── Position Monitor ──→ Position Details
            │
            ▼
    Portfolio Risk Assessment
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


class AssessmentLevel(str, Enum):
    """Portfolio risk assessment level."""
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class PortfolioRiskAssessment:
    """Comprehensive portfolio risk assessment result."""
    assessment_id: str
    account_id: str
    snapshot_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    level: AssessmentLevel = AssessmentLevel.NORMAL
    risk_score: float = 0.0

    # ---- Exposure ----
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    exposure_risk_score: float = 0.0

    # ---- PnL ----
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0
    daily_pnl: float = 0.0
    pnl_risk_score: float = 0.0

    # ---- Margin ----
    margin_used: float = 0.0
    margin_available: float = 0.0
    margin_ratio: float = 0.0
    margin_risk_score: float = 0.0

    # ---- Drawdown ----
    current_drawdown_pct: float = 0.0
    max_historical_drawdown_pct: float = 0.0
    drawdown_risk_score: float = 0.0

    # ---- Concentration ----
    top_holding_pct: float = 0.0
    sector_concentration: dict[str, float] = field(default_factory=dict)
    concentration_risk_score: float = 0.0

    # ---- Greeks ----
    portfolio_delta: float = 0.0
    portfolio_gamma: float = 0.0
    portfolio_theta: float = 0.0
    portfolio_vega: float = 0.0
    portfolio_rho: float = 0.0
    greeks_risk_score: float = 0.0

    # ---- Factor ----
    factor_exposures: dict[str, float] = field(default_factory=dict)
    factor_risk_score: float = 0.0

    # ---- Correlation ----
    max_pairwise_correlation: float = 0.0
    correlation_risk_score: float = 0.0

    # ---- Liquidity ----
    portfolio_liquidity_score: float = 100.0
    avg_exit_time_hours: float = 0.0
    liquidity_risk_score: float = 0.0

    # ---- Details ----
    breaches: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    evaluation_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "account_id": self.account_id,
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "risk_score": self.risk_score,
            "exposure": {
                "gross": self.gross_exposure,
                "net": self.net_exposure,
                "long": self.long_exposure,
                "short": self.short_exposure,
                "risk_score": self.exposure_risk_score,
            },
            "pnl": {
                "unrealized": self.total_unrealized_pnl,
                "realized": self.total_realized_pnl,
                "daily": self.daily_pnl,
                "risk_score": self.pnl_risk_score,
            },
            "margin": {
                "used": self.margin_used,
                "available": self.margin_available,
                "ratio": self.margin_ratio,
                "risk_score": self.margin_risk_score,
            },
            "drawdown": {
                "current_pct": self.current_drawdown_pct,
                "max_historical_pct": self.max_historical_drawdown_pct,
                "risk_score": self.drawdown_risk_score,
            },
            "concentration": {
                "top_holding_pct": self.top_holding_pct,
                "sector": dict(self.sector_concentration),
                "risk_score": self.concentration_risk_score,
            },
            "greeks": {
                "delta": self.portfolio_delta,
                "gamma": self.portfolio_gamma,
                "theta": self.portfolio_theta,
                "vega": self.portfolio_vega,
                "rho": self.portfolio_rho,
                "risk_score": self.greeks_risk_score,
            },
            "factor": {
                "exposures": dict(self.factor_exposures),
                "risk_score": self.factor_risk_score,
            },
            "correlation": {
                "max_pairwise": self.max_pairwise_correlation,
                "risk_score": self.correlation_risk_score,
            },
            "liquidity": {
                "score": self.portfolio_liquidity_score,
                "avg_exit_hours": self.avg_exit_time_hours,
                "risk_score": self.liquidity_risk_score,
            },
            "breaches": self.breaches,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "evaluation_time_ms": self.evaluation_time_ms,
        }


class PortfolioRiskEngine:
    """
    Unified portfolio-wide risk evaluation engine.

    Aggregates risk signals from all portfolio monitors and produces
    a comprehensive PortfolioRiskAssessment. This is the central
    engine for portfolio-level risk evaluation.

    Usage::

        engine = PortfolioRiskEngine()
        await engine.initialize()
        assessment = await engine.evaluate(snapshot)
        actions = await engine.generate_actions(assessment)
    """

    def __init__(self, engine_id: str = "PRE-01") -> None:
        self.engine_id = engine_id
        self._initialized = False
        self._eval_count: int = 0
        self._lock = asyncio.Lock()

        # Sub-engine references (lazy, set by initialize)
        self._exposure_engine: Any = None
        self._pnl_engine: Any = None
        self._margin_monitor: Any = None
        self._drawdown_monitor: Any = None
        self._concentration_engine: Any = None
        self._greeks_engine: Any = None
        self._factor_engine: Any = None
        self._correlation_monitor: Any = None
        self._liquidity_monitor: Any = None
        self._position_monitor: Any = None

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the portfolio risk engine and all sub-engines."""
        logger.info(f"PortfolioRiskEngine [{self.engine_id}] initializing...")
        self._initialized = True
        logger.info(f"PortfolioRiskEngine [{self.engine_id}] initialized.")

    async def stop(self) -> None:
        """Stop the engine."""
        self._initialized = False
        logger.info(f"PortfolioRiskEngine [{self.engine_id}] stopped.")

    # ---- Core API ----

    async def evaluate(self, snapshot: PortfolioSnapshot) -> dict[str, Any]:
        """
        Evaluate a portfolio snapshot and produce a risk assessment.

        Runs all sub-engine evaluations in parallel and aggregates
        results into a comprehensive assessment.
        """
        if not self._initialized:
            await self.initialize()

        t_start = time.perf_counter()

        async with self._lock:
            self._eval_count += 1

        # Run all evaluations in parallel
        (
            exposure_result,
            pnl_result,
            margin_result,
            drawdown_result,
            concentration_result,
            greeks_result,
            factor_result,
            correlation_result,
            liquidity_result,
            position_result,
        ) = await asyncio.gather(
            self._evaluate_exposure(snapshot),
            self._evaluate_pnl(snapshot),
            self._evaluate_margin(snapshot),
            self._evaluate_drawdown(snapshot),
            self._evaluate_concentration(snapshot),
            self._evaluate_greeks(snapshot),
            self._evaluate_factors(snapshot),
            self._evaluate_correlation(snapshot),
            self._evaluate_liquidity(snapshot),
            self._evaluate_positions(snapshot),
            return_exceptions=True,
        )

        # Aggregate
        assessment = PortfolioRiskAssessment(
            assessment_id=f"ASSESS-{self._eval_count:06d}",
            account_id=snapshot.account_id,
            snapshot_id=snapshot.snapshot_id,
        )

        self._merge_result(assessment, exposure_result, "exposure")
        self._merge_result(assessment, pnl_result, "pnl")
        self._merge_result(assessment, margin_result, "margin")
        self._merge_result(assessment, drawdown_result, "drawdown")
        self._merge_result(assessment, concentration_result, "concentration")
        self._merge_result(assessment, greeks_result, "greeks")
        self._merge_result(assessment, factor_result, "factor")
        self._merge_result(assessment, correlation_result, "correlation")
        self._merge_result(assessment, liquidity_result, "liquidity")

        # Compute aggregate risk score
        assessment.risk_score = self._compute_aggregate_score(assessment)

        # Determine level
        assessment.level = self._determine_level(assessment.risk_score)

        # Generate recommendations
        assessment.recommendations = self._generate_recommendations(assessment)

        assessment.evaluation_time_ms = (time.perf_counter() - t_start) * 1000

        logger.info(
            f"PortfolioRiskEngine [{self.engine_id}] evaluation: "
            f"{assessment.level.value} (score={assessment.risk_score:.1f}, "
            f"time={assessment.evaluation_time_ms:.1f}ms)"
        )

        return assessment.to_dict()

    async def monitor(self, snapshot: PortfolioSnapshot) -> dict[str, Any]:
        """Lightweight monitoring — returns only the risk level and score."""
        result = await self.evaluate(snapshot)
        return {
            "level": result["level"],
            "risk_score": result["risk_score"],
            "breaches": result["breaches"],
            "warnings": result["warnings"],
        }

    async def generate_actions(self, assessment: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Generate recommended risk actions based on assessment.

        Returns a list of recommended actions: reduce, hedge, pause, kill.
        """
        actions: list[dict[str, Any]] = []
        level = assessment.get("level", "NORMAL")
        risk_score = assessment.get("risk_score", 0)

        if level == "CRITICAL":
            actions.append({
                "type": "kill_switch",
                "priority": 1,
                "message": "Critical risk level — trigger kill switch",
            })
        elif level == "HIGH":
            actions.append({
                "type": "pause_strategies",
                "priority": 1,
                "message": "High risk — pause all automated strategies",
            })
            if assessment.get("exposure", {}).get("net", 0) != 0:
                actions.append({
                    "type": "reduce_positions",
                    "priority": 2,
                    "target_reduction_pct": 50,
                    "message": "Reduce net exposure by 50%",
                })

        if assessment.get("drawdown", {}).get("current_pct", 0) > 10:
            actions.append({
                "type": "reduce_positions",
                "priority": 2,
                "target_reduction_pct": 30,
                "message": f"Drawdown at {assessment['drawdown']['current_pct']:.1f}% — reduce positions",
            })

        if assessment.get("margin", {}).get("ratio", 0) > 0.8:
            actions.append({
                "type": "reduce_margin",
                "priority": 1,
                "message": "Margin ratio critical — reduce margin usage",
            })

        if assessment.get("concentration", {}).get("top_holding_pct", 0) > 30:
            actions.append({
                "type": "diversify",
                "priority": 3,
                "message": "High concentration — diversify holdings",
            })

        return actions

    # ---- Stats ----

    async def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        async with self._lock:
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

    # ---- Internal: Sub-Engine Evaluations ----

    async def _evaluate_exposure(self, snapshot: PortfolioSnapshot) -> dict[str, Any]:
        """Evaluate exposure risk from snapshot."""
        total = snapshot.total_equity or 1.0
        gross_pct = (snapshot.gross_exposure / total) * 100 if total > 0 else 0
        net_pct = (snapshot.net_exposure / total) * 100 if total > 0 else 0

        risk_score = 0.0
        breaches = []
        if gross_pct > 200:
            risk_score += 30
            breaches.append({"type": "exposure", "message": f"Gross exposure {gross_pct:.1f}% > 200%"})
        elif gross_pct > 150:
            risk_score += 15
        if abs(net_pct) > 100:
            risk_score += 20

        return {
            "gross_exposure": snapshot.gross_exposure,
            "net_exposure": snapshot.net_exposure,
            "long_exposure": snapshot.long_exposure,
            "short_exposure": snapshot.short_exposure,
            "exposure_risk_score": min(risk_score, 100),
            "breaches": breaches,
        }

    async def _evaluate_pnl(self, snapshot: PortfolioSnapshot) -> dict[str, Any]:
        """Evaluate PnL risk from snapshot."""
        risk_score = 0.0
        breaches = []

        total = snapshot.total_equity or 1.0
        daily_pnl_pct = (snapshot.daily_pnl / total) * 100 if total > 0 else 0
        if daily_pnl_pct < -5:
            risk_score += 40
            breaches.append({"type": "pnl", "message": f"Daily PnL {daily_pnl_pct:.2f}% < -5%"})
        elif daily_pnl_pct < -2:
            risk_score += 20
        elif daily_pnl_pct < -1:
            risk_score += 10

        return {
            "total_unrealized_pnl": snapshot.total_unrealized_pnl,
            "total_realized_pnl": snapshot.total_realized_pnl,
            "daily_pnl": snapshot.daily_pnl,
            "pnl_risk_score": min(risk_score, 100),
            "breaches": breaches,
        }

    async def _evaluate_margin(self, snapshot: PortfolioSnapshot) -> dict[str, Any]:
        """Evaluate margin risk from snapshot."""
        risk_score = 0.0
        breaches = []
        margin_ratio = snapshot.margin_ratio

        if margin_ratio > 0.95:
            risk_score += 50
            breaches.append({"type": "margin", "message": f"Margin ratio {margin_ratio:.1%} critical"})
        elif margin_ratio > 0.8:
            risk_score += 30
            breaches.append({"type": "margin", "message": f"Margin ratio {margin_ratio:.1%} high"})
        elif margin_ratio > 0.6:
            risk_score += 15

        return {
            "margin_used": snapshot.margin_used,
            "margin_available": snapshot.margin_available,
            "margin_ratio": snapshot.margin_ratio,
            "margin_risk_score": min(risk_score, 100),
            "breaches": breaches,
        }

    async def _evaluate_drawdown(self, snapshot: PortfolioSnapshot) -> dict[str, Any]:
        """Evaluate drawdown risk from snapshot."""
        risk_score = 0.0
        breaches = []
        dd = snapshot.current_drawdown_pct

        if dd > 20:
            risk_score += 40
            breaches.append({"type": "drawdown", "message": f"Drawdown {dd:.1f}% > 20%"})
        elif dd > 10:
            risk_score += 25
        elif dd > 5:
            risk_score += 10

        if snapshot.max_historical_drawdown_pct > 30:
            risk_score += 20

        return {
            "current_drawdown_pct": dd,
            "max_historical_drawdown_pct": snapshot.max_historical_drawdown_pct,
            "drawdown_risk_score": min(risk_score, 100),
            "breaches": breaches,
        }

    async def _evaluate_concentration(self, snapshot: PortfolioSnapshot) -> dict[str, Any]:
        """Evaluate concentration risk from snapshot."""
        risk_score = 0.0
        breaches = []

        top = snapshot.top_holding_pct
        if top > 40:
            risk_score += 35
            breaches.append({"type": "concentration", "message": f"Top holding {top:.1f}% > 40%"})
        elif top > 25:
            risk_score += 20
        elif top > 15:
            risk_score += 10

        for sector, pct in snapshot.sector_concentration.items():
            if pct > 50:
                risk_score += 15
                breaches.append({"type": "concentration", "message": f"Sector {sector} at {pct:.1f}% > 50%"})

        return {
            "top_holding_pct": top,
            "sector_concentration": dict(snapshot.sector_concentration),
            "concentration_risk_score": min(risk_score, 100),
            "breaches": breaches,
        }

    async def _evaluate_greeks(self, snapshot: PortfolioSnapshot) -> dict[str, Any]:
        """Evaluate Greeks risk from snapshot."""
        risk_score = 0.0
        total = snapshot.total_equity or 1.0

        if total > 0 and abs(snapshot.portfolio_delta) / total > 0.1:
            risk_score += 15
        if abs(snapshot.portfolio_gamma) > 1.0:
            risk_score += 20
        if abs(snapshot.portfolio_theta) > 500:
            risk_score += 10
        if abs(snapshot.portfolio_vega) > 1000:
            risk_score += 15

        return {
            "portfolio_delta": snapshot.portfolio_delta,
            "portfolio_gamma": snapshot.portfolio_gamma,
            "portfolio_theta": snapshot.portfolio_theta,
            "portfolio_vega": snapshot.portfolio_vega,
            "portfolio_rho": snapshot.portfolio_rho,
            "greeks_risk_score": min(risk_score, 100),
        }

    async def _evaluate_factors(self, snapshot: PortfolioSnapshot) -> dict[str, Any]:
        """Evaluate factor exposure risk from snapshot."""
        risk_score = 0.0
        exposures = snapshot.factor_exposures

        for factor, value in exposures.items():
            if abs(value) > 2.0:
                risk_score += 15
            elif abs(value) > 1.5:
                risk_score += 10

        return {
            "factor_exposures": dict(exposures),
            "factor_risk_score": min(risk_score, 100),
        }

    async def _evaluate_correlation(self, snapshot: PortfolioSnapshot) -> dict[str, Any]:
        """Evaluate correlation risk from snapshot."""
        risk_score = 0.0
        max_corr = 0.0
        matrix = snapshot.correlation_matrix

        for sym_a, row in matrix.items():
            for sym_b, corr in row.items():
                if sym_a != sym_b and corr > max_corr:
                    max_corr = corr

        if max_corr > 0.9:
            risk_score += 30
        elif max_corr > 0.7:
            risk_score += 15
        elif max_corr > 0.5:
            risk_score += 5

        return {
            "max_pairwise_correlation": max_corr,
            "correlation_risk_score": min(risk_score, 100),
        }

    async def _evaluate_liquidity(self, snapshot: PortfolioSnapshot) -> dict[str, Any]:
        """Evaluate liquidity risk from snapshot."""
        risk_score = 0.0
        breaches = []
        score = snapshot.portfolio_liquidity_score

        if score < 20:
            risk_score += 35
            breaches.append({"type": "liquidity", "message": f"Liquidity score {score:.1f} critically low"})
        elif score < 40:
            risk_score += 20
        elif score < 60:
            risk_score += 10

        if snapshot.avg_exit_time_hours > 24:
            risk_score += 20
            breaches.append({"type": "liquidity", "message": f"Avg exit time {snapshot.avg_exit_time_hours:.1f}h > 24h"})

        return {
            "portfolio_liquidity_score": score,
            "avg_exit_time_hours": snapshot.avg_exit_time_hours,
            "liquidity_risk_score": min(risk_score, 100),
            "breaches": breaches,
        }

    async def _evaluate_positions(self, snapshot: PortfolioSnapshot) -> dict[str, Any]:
        """Evaluate position-level details."""
        losing_positions = 0
        for pos in snapshot.positions.values():
            if pos.unrealized_pnl < 0:
                losing_positions += 1

        return {
            "total_positions": len(snapshot.positions),
            "losing_positions": losing_positions,
        }

    # ---- Internal: Aggregation ----

    def _merge_result(
        self, assessment: PortfolioRiskAssessment, result: Any, category: str
    ) -> None:
        """Merge a sub-engine result into the assessment."""
        if isinstance(result, Exception):
            logger.error(f"Sub-engine [{category}] error: {result}")
            return
        if not isinstance(result, dict):
            return

        if category == "exposure":
            assessment.gross_exposure = result.get("gross_exposure", 0)
            assessment.net_exposure = result.get("net_exposure", 0)
            assessment.long_exposure = result.get("long_exposure", 0)
            assessment.short_exposure = result.get("short_exposure", 0)
            assessment.exposure_risk_score = result.get("exposure_risk_score", 0)
        elif category == "pnl":
            assessment.total_unrealized_pnl = result.get("total_unrealized_pnl", 0)
            assessment.total_realized_pnl = result.get("total_realized_pnl", 0)
            assessment.daily_pnl = result.get("daily_pnl", 0)
            assessment.pnl_risk_score = result.get("pnl_risk_score", 0)
        elif category == "margin":
            assessment.margin_used = result.get("margin_used", 0)
            assessment.margin_available = result.get("margin_available", 0)
            assessment.margin_ratio = result.get("margin_ratio", 0)
            assessment.margin_risk_score = result.get("margin_risk_score", 0)
        elif category == "drawdown":
            assessment.current_drawdown_pct = result.get("current_drawdown_pct", 0)
            assessment.max_historical_drawdown_pct = result.get("max_historical_drawdown_pct", 0)
            assessment.drawdown_risk_score = result.get("drawdown_risk_score", 0)
        elif category == "concentration":
            assessment.top_holding_pct = result.get("top_holding_pct", 0)
            assessment.sector_concentration = result.get("sector_concentration", {})
            assessment.concentration_risk_score = result.get("concentration_risk_score", 0)
        elif category == "greeks":
            assessment.portfolio_delta = result.get("portfolio_delta", 0)
            assessment.portfolio_gamma = result.get("portfolio_gamma", 0)
            assessment.portfolio_theta = result.get("portfolio_theta", 0)
            assessment.portfolio_vega = result.get("portfolio_vega", 0)
            assessment.portfolio_rho = result.get("portfolio_rho", 0)
            assessment.greeks_risk_score = result.get("greeks_risk_score", 0)
        elif category == "factor":
            assessment.factor_exposures = result.get("factor_exposures", {})
            assessment.factor_risk_score = result.get("factor_risk_score", 0)
        elif category == "correlation":
            assessment.max_pairwise_correlation = result.get("max_pairwise_correlation", 0)
            assessment.correlation_risk_score = result.get("correlation_risk_score", 0)
        elif category == "liquidity":
            assessment.portfolio_liquidity_score = result.get("portfolio_liquidity_score", 100)
            assessment.avg_exit_time_hours = result.get("avg_exit_time_hours", 0)
            assessment.liquidity_risk_score = result.get("liquidity_risk_score", 0)

        assessment.breaches.extend(result.get("breaches", []))

    def _compute_aggregate_score(self, assessment: PortfolioRiskAssessment) -> float:
        """Compute weighted aggregate risk score."""
        scores = {
            assessment.exposure_risk_score: 0.15,
            assessment.pnl_risk_score: 0.15,
            assessment.margin_risk_score: 0.15,
            assessment.drawdown_risk_score: 0.15,
            assessment.concentration_risk_score: 0.10,
            assessment.greeks_risk_score: 0.10,
            assessment.factor_risk_score: 0.05,
            assessment.correlation_risk_score: 0.05,
            assessment.liquidity_risk_score: 0.10,
        }
        weighted = sum(score * weight for score, weight in scores.items())
        return min(weighted, 100.0)

    def _determine_level(self, risk_score: float) -> AssessmentLevel:
        """Determine risk level from aggregate score."""
        if risk_score >= 80:
            return AssessmentLevel.CRITICAL
        elif risk_score >= 60:
            return AssessmentLevel.HIGH
        elif risk_score >= 40:
            return AssessmentLevel.ELEVATED
        elif risk_score >= 20:
            return AssessmentLevel.WARNING
        return AssessmentLevel.NORMAL

    def _generate_recommendations(self, assessment: PortfolioRiskAssessment) -> list[str]:
        """Generate actionable recommendations from assessment."""
        recs = []

        if assessment.drawdown_risk_score > 50:
            recs.append("Reduce position sizes to limit further drawdown")
        if assessment.margin_risk_score > 50:
            recs.append("Reduce margin usage by closing or hedging positions")
        if assessment.concentration_risk_score > 50:
            recs.append("Diversify portfolio to reduce concentration risk")
        if assessment.liquidity_risk_score > 50:
            recs.append("Avoid adding illiquid positions; consider exit plan")
        if assessment.correlation_risk_score > 50:
            recs.append("Reduce correlated positions to improve diversification")
        if assessment.exposure_risk_score > 50:
            recs.append("Reduce gross exposure to stay within limits")
        if assessment.greeks_risk_score > 50:
            recs.append("Hedge Greeks exposure to reduce directional risk")

        return recs if recs else ["Portfolio risk within acceptable levels"]
