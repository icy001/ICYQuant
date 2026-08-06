"""Factor Report — automatic factor research report generator.

Generates comprehensive reports covering::

    IC, RankIC, ICIR, Decay, Turnover, Exposure, Correlation, Summary

Produces complete institutional-grade research reports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReportSection(str, Enum):
    """Report section identifiers."""

    SUMMARY = "summary"
    IC = "ic"
    RANKIC = "rankic"
    ICIR = "icir"
    DECAY = "decay"
    TURNOVER = "turnover"
    EXPOSURE = "exposure"
    CORRELATION = "correlation"
    QUANTILE = "quantile"
    ALPHA_POOL = "alpha_pool"
    RECOMMENDATION = "recommendation"


@dataclass
class FactorReport:
    """Comprehensive factor research report.

    Generates a structured report covering all evaluation dimensions,
    suitable for institutional research workflows.
    """

    report_id: str = ""
    factor_name: str = ""
    factor_type: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sections: Dict[str, Any] = field(default_factory=dict)
    overall_rating: str = ""
    recommendation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_section(self, name: str, content: Any) -> None:
        self.sections[name] = content

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "factor_name": self.factor_name,
            "factor_type": self.factor_type,
            "generated_at": self.generated_at.isoformat(),
            "sections": self.sections,
            "overall_rating": self.overall_rating,
            "recommendation": self.recommendation,
            "metadata": self.metadata,
        }

    async def generate(
        self,
        factor: Dict[str, Any],
        evaluations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate a complete factor research report.

        Args:
            factor: factor entity dict
            evaluations: list of evaluation result dicts

        Returns:
            report dict
        """
        self.factor_name = factor.get("name", "Unknown")
        self.factor_type = factor.get("factor_type", "custom")
        self.report_id = f"report_{factor.get('id', 'unknown')}"

        # Aggregate evaluation results
        eval_data = self._aggregate_evaluations(evaluations)

        # Build each section
        self._build_summary_section(factor, eval_data)
        self._build_ic_section(eval_data)
        self._build_rankic_section(eval_data)
        self._build_icir_section(eval_data)
        self._build_decay_section(eval_data)
        self._build_turnover_section(eval_data)
        self._build_exposure_section(eval_data)
        self._build_correlation_section(eval_data)
        self._build_quantile_section(eval_data)
        self._build_recommendation_section(eval_data)

        # Determine overall rating
        self.overall_rating = self._determine_rating(eval_data)

        return self.to_dict()

    def _aggregate_evaluations(
        self, evaluations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aggregate multiple evaluation results."""
        aggregated: Dict[str, Any] = {}

        for eval_item in evaluations:
            metrics = eval_item.get("metrics", eval_item)
            if "evaluations" in metrics:
                for key, val in metrics["evaluations"].items():
                    aggregated[key] = val
            else:
                for key, val in metrics.items():
                    if key not in ("factor_id", "factor_name", "eval_type"):
                        aggregated[key] = val

        return aggregated

    def _build_summary_section(
        self, factor: Dict[str, Any], eval_data: Dict[str, Any]
    ) -> None:
        self.sections[ReportSection.SUMMARY.value] = {
            "factor_name": factor.get("name"),
            "factor_type": factor.get("factor_type"),
            "created_at": factor.get("created_at"),
            "version": factor.get("version", 1),
            "tags": factor.get("tags", []),
            "evaluation_count": len(eval_data),
        }

    def _build_ic_section(self, eval_data: Dict[str, Any]) -> None:
        ic_data = eval_data.get("ic", {})
        self.sections[ReportSection.IC.value] = {
            "mean_ic": ic_data.get("mean_ic", 0.0),
            "std_ic": ic_data.get("std_ic", 0.0),
            "positive_ratio": ic_data.get("ic_positive_ratio", 0.0),
            "distribution": ic_data.get("ic_distribution", {}),
        }

    def _build_rankic_section(self, eval_data: Dict[str, Any]) -> None:
        rankic_data = eval_data.get("rankic", {})
        self.sections[ReportSection.RANKIC.value] = {
            "mean_rankic": rankic_data.get("mean_rankic", 0.0),
            "std_rankic": rankic_data.get("std_rankic", 0.0),
            "positive_ratio": rankic_data.get("rankic_positive_ratio", 0.0),
            "rank_stability": rankic_data.get("rank_stability", 0.0),
        }

    def _build_icir_section(self, eval_data: Dict[str, Any]) -> None:
        icir_data = eval_data.get("icir", {})
        self.sections[ReportSection.ICIR.value] = {
            "icir": icir_data.get("icir", 0.0),
            "rank_icir": icir_data.get("rank_icir", 0.0),
            "t_statistic": icir_data.get("t_statistic", 0.0),
            "quality": icir_data.get("metadata", {}).get("quality", "unknown"),
        }

    def _build_decay_section(self, eval_data: Dict[str, Any]) -> None:
        decay_data = eval_data.get("decay", {})
        self.sections[ReportSection.DECAY.value] = {
            "ic_by_horizon": decay_data.get("ic_by_horizon", {}),
            "half_life": decay_data.get("half_life"),
            "decay_rate": decay_data.get("decay_rate", 0.0),
        }

    def _build_turnover_section(self, eval_data: Dict[str, Any]) -> None:
        turnover_data = eval_data.get("turnover", {})
        self.sections[ReportSection.TURNOVER.value] = {
            "avg_turnover": turnover_data.get("avg_turnover", 0.0),
            "turnover_std": turnover_data.get("turnover_std", 0.0),
            "signal_stability": turnover_data.get("signal_stability", 0.0),
            "holding_persistence": turnover_data.get("holding_persistence", 0.0),
        }

    def _build_exposure_section(self, eval_data: Dict[str, Any]) -> None:
        exposure_data = eval_data.get("exposure", {})
        self.sections[ReportSection.EXPOSURE.value] = {
            "market_cap_exposure": exposure_data.get("market_cap_exposure", 0.0),
            "sector_exposure": exposure_data.get("sector_exposure", {}),
            "style_exposures": exposure_data.get("style_exposures", {}),
            "concentration": exposure_data.get("concentration", 0.0),
        }

    def _build_correlation_section(self, eval_data: Dict[str, Any]) -> None:
        corr_data = eval_data.get("correlation", {})
        self.sections[ReportSection.CORRELATION.value] = {
            "high_correlation_pairs": corr_data.get("high_correlation_pairs", []),
            "redundant_factors": corr_data.get("redundant_factors", []),
        }

    def _build_quantile_section(self, eval_data: Dict[str, Any]) -> None:
        quantile_data = eval_data.get("quantile", {})
        self.sections[ReportSection.QUANTILE.value] = {
            "groups": quantile_data.get("groups", []),
            "spread": quantile_data.get("spread", {}),
        }

    def _build_recommendation_section(self, eval_data: Dict[str, Any]) -> None:
        """Generate automated recommendation based on evaluation results."""
        score = 0
        reasons: List[str] = []

        # ICIR scoring
        icir_data = eval_data.get("icir", {})
        icir = icir_data.get("icir", 0.0)
        if abs(icir) >= 0.5:
            score += 30
            reasons.append("Excellent ICIR")
        elif abs(icir) >= 0.3:
            score += 20
            reasons.append("Good ICIR")
        elif abs(icir) >= 0.1:
            score += 10
            reasons.append("Acceptable ICIR")

        # IC scoring
        ic_data = eval_data.get("ic", {})
        mean_ic = ic_data.get("mean_ic", 0.0)
        if abs(mean_ic) >= 0.05:
            score += 20
            reasons.append("Strong IC")
        elif abs(mean_ic) >= 0.02:
            score += 10
            reasons.append("Moderate IC")

        # Turnover
        turnover_data = eval_data.get("turnover", {})
        avg_turnover = turnover_data.get("avg_turnover", 0.0)
        if avg_turnover <= 0.3:
            score += 20
            reasons.append("Low turnover")
        elif avg_turnover <= 0.5:
            score += 10
            reasons.append("Moderate turnover")
        else:
            reasons.append("High turnover")

        # Decay
        decay_data = eval_data.get("decay", {})
        half_life = decay_data.get("half_life")
        if half_life is not None:
            if half_life >= 30:
                score += 15
                reasons.append("Long half-life")
            elif half_life >= 10:
                score += 10
                reasons.append("Moderate half-life")

        # Exposure neutrality
        exposure_data = eval_data.get("exposure", {})
        market_cap_exp = abs(exposure_data.get("market_cap_exposure", 0.0))
        if market_cap_exp < 0.1:
            score += 15
            reasons.append("Low market cap bias")

        # Determine recommendation
        if score >= 70:
            recommendation = "STRONG_BUY — Recommend immediate production deployment"
        elif score >= 50:
            recommendation = "BUY — Recommend production deployment with monitoring"
        elif score >= 30:
            recommendation = "HOLD — Further research recommended"
        else:
            recommendation = "REJECT — Does not meet quality thresholds"

        self.sections[ReportSection.RECOMMENDATION.value] = {
            "score": score,
            "max_score": 100,
            "reasons": reasons,
            "recommendation": recommendation,
        }
        self.recommendation = recommendation

    def _determine_rating(self, eval_data: Dict[str, Any]) -> str:
        """Determine overall factor rating."""
        icir_data = eval_data.get("icir", {})
        icir = abs(icir_data.get("icir", 0.0))

        if icir >= 0.5:
            return "★★★★★ Excellent"
        elif icir >= 0.3:
            return "★★★★ Good"
        elif icir >= 0.15:
            return "★★★ Acceptable"
        elif icir >= 0.05:
            return "★★ Weak"
        else:
            return "★ Poor"
