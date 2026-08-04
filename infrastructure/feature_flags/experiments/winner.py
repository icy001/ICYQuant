"""
Experiment winner selection.

Determines the winning variant of an
experiment based on statistical analysis
and configurable criteria.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .analyzer import AnalysisResult, ExperimentAnalyzer
from .statistics import VariantStats


class WinnerSelector:
    """
    Selects the winning variant of an experiment.

    Supports manual and automatic winner
    selection based on statistical significance,
    effect size, and business criteria.

    Usage:
        selector = WinnerSelector(min_confidence=0.95, min_lift=0.05)
        result = selector.select(control_stats, treatment_stats)
        if result.has_winner:
            print(f"Winner: {result.winner_id}")
    """

    def __init__(
        self,
        min_confidence: float = 0.95,
        min_lift: float = 0.0,
        min_sample_size: int = 100,
        mode: str = "automatic",
    ) -> None:
        """
        Initialize the winner selector.

        Args:
            min_confidence: Minimum confidence level required.
            min_lift: Minimum lift (relative improvement) required.
            min_sample_size: Minimum sample size per variant.
            mode: Selection mode (automatic or manual).
        """
        self._min_confidence = min_confidence
        self._min_lift = min_lift
        self._min_sample_size = min_sample_size
        self._mode = mode
        self._analyzer = ExperimentAnalyzer()

    def select(
        self,
        control_stats: VariantStats,
        treatment_stats: VariantStats,
        metric_type: str = "conversion",
    ) -> WinnerResult:
        """
        Evaluate and potentially select a winner.

        Args:
            control_stats: Control group statistics.
            treatment_stats: Treatment group statistics.
            metric_type: Metric type for analysis.

        Returns:
            WinnerResult with selection details.
        """
        result = WinnerResult()

        # Check sample size
        if control_stats.sample_size < self._min_sample_size:
            result.reason = (
                f"Insufficient control samples: "
                f"{control_stats.sample_size} < {self._min_sample_size}"
            )
            return result

        if treatment_stats.sample_size < self._min_sample_size:
            result.reason = (
                f"Insufficient treatment samples: "
                f"{treatment_stats.sample_size} < {self._min_sample_size}"
            )
            return result

        # Run analysis
        analysis = self._analyzer.analyze(
            control_stats, treatment_stats,
            confidence=self._min_confidence,
            metric_type=metric_type,
        )
        result.analysis = analysis

        # Check significance
        if not analysis.is_significant:
            result.reason = f"Not significant: p_value={analysis.p_value:.4f}"
            return result

        # Check lift
        if analysis.lift < self._min_lift:
            result.reason = f"Insufficient lift: {analysis.lift:.4f} < {self._min_lift}"
            return result

        # Check if treatment outperforms control
        if metric_type == "conversion":
            treatment_better = treatment_stats.conversion_rate > control_stats.conversion_rate
        else:
            treatment_better = treatment_stats.average_value > control_stats.average_value

        if treatment_better:
            result.has_winner = True
            result.winner_id = treatment_stats.variant_id
            result.reason = "Treatment significantly outperforms control"
        else:
            result.has_winner = False
            result.winner_id = control_stats.variant_id
            result.reason = "Control outperforms treatment (no winner declared)"

        return result


class WinnerResult:
    """
    Result of winner selection.

    Attributes:
        has_winner: Whether a winner was selected.
        winner_id: ID of the winning variant.
        reason: Reason for the decision.
        analysis: Statistical analysis result.
    """

    def __init__(
        self,
        has_winner: bool = False,
        winner_id: str = "",
        reason: str = "",
        analysis: Optional[AnalysisResult] = None,
    ) -> None:
        self.has_winner = has_winner
        self.winner_id = winner_id
        self.reason = reason
        self.analysis = analysis

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "has_winner": self.has_winner,
            "winner_id": self.winner_id,
            "reason": self.reason,
            "analysis": self.analysis.to_dict() if self.analysis else None,
        }
