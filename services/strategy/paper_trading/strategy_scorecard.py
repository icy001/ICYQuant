"""
Strategy Scorecard
==================
Comprehensive strategy evaluation scorecard used for promotion decisions.

Dimensions:
    Profitability     — Return metrics
    Risk              — Drawdown, volatility, VaR
    Stability         — Consistency, win rate persistence
    Execution Quality  — Slippage, fill rates
    Capacity          — Scalability estimates
    Overall Score     — Weighted composite
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ScoreDimension(str, Enum):
    PROFITABILITY = "profitability"
    RISK = "risk"
    STABILITY = "stability"
    EXECUTION_QUALITY = "execution_quality"
    CAPACITY = "capacity"


@dataclass
class DimensionScore:
    """Score for a single evaluation dimension."""
    dimension: ScoreDimension
    score: float = 0.0      # 0-100
    weight: float = 0.2
    weighted_score: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)
    grade: str = "F"        # A-F grade
    commentary: str = ""


@dataclass
class ScorecardResult:
    """Full strategy scorecard."""
    scorecard_id: str = ""
    strategy_id: str = ""
    session_id: str = ""
    overall_score: float = 0.0        # 0-100
    overall_grade: str = "F"           # A-F
    dimensions: List[DimensionScore] = field(default_factory=list)
    recommendation: str = ""            # PROMOTE / WATCH / REJECT
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scorecard_id": self.scorecard_id,
            "strategy_id": self.strategy_id,
            "overall_score": round(self.overall_score, 1),
            "overall_grade": self.overall_grade,
            "recommendation": self.recommendation,
            "dimensions": [
                {
                    "dimension": d.dimension.value,
                    "score": round(d.score, 1),
                    "weight": d.weight,
                    "grade": d.grade,
                    "commentary": d.commentary,
                }
                for d in self.dimensions
            ],
            "generated_at": self.generated_at.isoformat(),
        }


class StrategyScorecard:
    """Generates comprehensive strategy evaluation scorecards.

    Used as the basis for paper-to-live promotion decisions.
    """

    # Default weights per dimension
    DEFAULT_WEIGHTS: Dict[ScoreDimension, float] = {
        ScoreDimension.PROFITABILITY: 0.30,
        ScoreDimension.RISK: 0.25,
        ScoreDimension.STABILITY: 0.20,
        ScoreDimension.EXECUTION_QUALITY: 0.15,
        ScoreDimension.CAPACITY: 0.10,
    }

    # Promotion thresholds
    PROMOTE_THRESHOLD: float = 70.0
    WATCH_THRESHOLD: float = 50.0

    def __init__(self):
        self._weights = dict(self.DEFAULT_WEIGHTS)
        self._scoring_functions: Dict[str, Any] = {}
        self.is_initialized = False

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("StrategyScorecard initialized")

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    async def score(self, strategy_id: str, session_id: str,
                    performance: Optional[Dict[str, Any]] = None,
                    risk_metrics: Optional[Dict[str, Any]] = None,
                    execution_metrics: Optional[Dict[str, Any]] = None,
                    ) -> ScorecardResult:
        """Generate a full strategy scorecard."""
        perf = performance or {}
        risk = risk_metrics or {}
        exec_m = execution_metrics or {}

        dimensions = []

        # Profitability
        profit_score = self._score_profitability(perf)
        dimensions.append(profit_score)

        # Risk
        risk_score = self._score_risk(risk)
        dimensions.append(risk_score)

        # Stability
        stability_score = self._score_stability(perf)
        dimensions.append(stability_score)

        # Execution Quality
        exec_score = self._score_execution(exec_m)
        dimensions.append(exec_score)

        # Capacity
        capacity_score = self._score_capacity(perf)
        dimensions.append(capacity_score)

        # Weighted overall
        for d in dimensions:
            d.weighted_score = d.score * self._weights.get(d.dimension, 0.2)

        overall = sum(d.weighted_score for d in dimensions)

        # Recommendation
        if overall >= self.PROMOTE_THRESHOLD:
            recommendation = "PROMOTE"
        elif overall >= self.WATCH_THRESHOLD:
            recommendation = "WATCH"
        else:
            recommendation = "REJECT"

        return ScorecardResult(
            scorecard_id=f"sc_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            strategy_id=strategy_id,
            session_id=session_id,
            overall_score=overall,
            overall_grade=self._grade(overall),
            dimensions=dimensions,
            recommendation=recommendation,
        )

    # ------------------------------------------------------------------
    # Dimension Scoring
    # ------------------------------------------------------------------

    def _score_profitability(self, perf: Dict[str, Any]) -> DimensionScore:
        sharpe = perf.get("sharpe_ratio", 0)
        total_return = perf.get("total_return", 0)
        profit_factor = perf.get("profit_factor", 0)

        score = 50.0
        score += min(sharpe * 20, 30)        # Up to +30 for Sharpe
        score += min(total_return * 50, 20)   # Up to +20 for return
        score += min(profit_factor * 5, 10)   # Up to +10 for profit factor
        score = max(0, min(100, score))

        return DimensionScore(
            dimension=ScoreDimension.PROFITABILITY,
            score=score,
            weight=self._weights[ScoreDimension.PROFITABILITY],
            metrics={"sharpe": sharpe, "total_return": total_return,
                     "profit_factor": profit_factor},
            grade=self._grade(score),
        )

    def _score_risk(self, risk: Dict[str, Any]) -> DimensionScore:
        max_dd = abs(risk.get("max_drawdown", 0))
        volatility = risk.get("annualized_volatility", 0)
        sortino = risk.get("sortino_ratio", 0)

        score = 60.0
        score -= max_dd * 100          # Deduct for drawdown
        score -= max(volatility - 0.15, 0) * 100  # Deduct for high vol
        score += min(sortino * 10, 20) # Bonus for Sortino
        score = max(0, min(100, score))

        return DimensionScore(
            dimension=ScoreDimension.RISK,
            score=score,
            weight=self._weights[ScoreDimension.RISK],
            metrics={"max_drawdown": max_dd, "volatility": volatility},
            grade=self._grade(score),
        )

    def _score_stability(self, perf: Dict[str, Any]) -> DimensionScore:
        win_rate = perf.get("win_rate", 0)
        calmar = perf.get("calmar_ratio", 0)
        total_trades = perf.get("total_trades", 0)

        score = 50.0
        score += (win_rate - 0.4) * 100  # Base on win rate
        score += min(calmar * 10, 20)    # Bonus for Calmar
        score += min(total_trades / 10, 10)  # Bonus for sample size
        score = max(0, min(100, score))

        return DimensionScore(
            dimension=ScoreDimension.STABILITY,
            score=score,
            weight=self._weights[ScoreDimension.STABILITY],
            metrics={"win_rate": win_rate, "calmar": calmar, "total_trades": total_trades},
            grade=self._grade(score),
        )

    def _score_execution(self, exec_m: Dict[str, Any]) -> DimensionScore:
        fill_rate = exec_m.get("fill_rate", 1.0)
        avg_slippage_bps = abs(exec_m.get("avg_slippage_bps", 0))

        score = 70.0
        score += (fill_rate - 0.9) * 200
        score -= avg_slippage_bps * 2
        score = max(0, min(100, score))

        return DimensionScore(
            dimension=ScoreDimension.EXECUTION_QUALITY,
            score=score,
            weight=self._weights[ScoreDimension.EXECUTION_QUALITY],
            metrics={"fill_rate": fill_rate, "avg_slippage_bps": avg_slippage_bps},
            grade=self._grade(score),
        )

    def _score_capacity(self, perf: Dict[str, Any]) -> DimensionScore:
        turnover = perf.get("turnover", 0)
        capacity_estimate = perf.get("capacity_estimate", 0)

        score = 60.0
        score -= min(turnover * 10, 30)          # Lower turnover is better
        score += min(capacity_estimate / 10000, 20)  # Higher capacity is better
        score = max(0, min(100, score))

        return DimensionScore(
            dimension=ScoreDimension.CAPACITY,
            score=score,
            weight=self._weights[ScoreDimension.CAPACITY],
            metrics={"turnover": turnover, "capacity_estimate": capacity_estimate},
            grade=self._grade(score),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _grade(self, score: float) -> str:
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def set_weights(self, weights: Dict[ScoreDimension, float]) -> None:
        self._weights.update(weights)

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "promote_threshold": self.PROMOTE_THRESHOLD,
            "watch_threshold": self.WATCH_THRESHOLD,
            "weights": {k.value: v for k, v in self._weights.items()},
        }
