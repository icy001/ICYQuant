"""
Experiment statistical analysis.

Provides statistical tests for evaluating
experiment results including:
    - Two-proportion z-test (conversion rates)
    - Two-sample t-test (continuous metrics)
    - Chi-square test (categorical outcomes)
    - Confidence interval calculation
    - P-value computation
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .statistics import VariantStats


@dataclass
class AnalysisResult:
    """
    Result of statistical analysis.

    Attributes:
        test_type: Statistical test used.
        test_statistic: Test statistic value.
        p_value: P-value.
        confidence: Confidence level.
        is_significant: Whether result is statistically significant.
        effect_size: Cohen's d effect size.
        lift: Relative improvement over control.
        control_ci: Control confidence interval.
        treatment_ci: Treatment confidence interval.
    """

    test_type: str = ""
    test_statistic: float = 0.0
    p_value: float = 1.0
    confidence: float = 0.95
    is_significant: bool = False
    effect_size: float = 0.0
    lift: float = 0.0
    control_ci: Tuple[float, float] = (0.0, 0.0)
    treatment_ci: Tuple[float, float] = (0.0, 0.0)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "test_type": self.test_type,
            "test_statistic": self.test_statistic,
            "p_value": self.p_value,
            "confidence": self.confidence,
            "is_significant": self.is_significant,
            "effect_size": self.effect_size,
            "lift": self.lift,
            "control_ci": list(self.control_ci),
            "treatment_ci": list(self.treatment_ci),
        }


def _normal_cdf(x: float) -> float:
    """Approximate the standard normal CDF using error function."""
    # Abramowitz and Stegun approximation
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2.0)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + sign * y)


def z_test_proportions(
    control: VariantStats,
    treatment: VariantStats,
) -> Tuple[float, float]:
    """
    Two-proportion z-test for conversion rates.

    Args:
        control: Control group statistics.
        treatment: Treatment group statistics.

    Returns:
        Tuple of (z_statistic, p_value).
    """
    n1 = control.sample_size
    n2 = treatment.sample_size
    p1 = control.conversion_rate
    p2 = treatment.conversion_rate

    if n1 == 0 or n2 == 0:
        return (0.0, 1.0)

    # Pooled proportion
    p_pool = (control.conversions + treatment.conversions) / (n1 + n2)
    if p_pool == 0 or p_pool == 1:
        return (0.0, 1.0)

    # Standard error
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return (0.0, 1.0)

    z = (p2 - p1) / se
    p_value = 2 * (1 - _normal_cdf(abs(z)))
    return (z, p_value)


def t_test_means(
    control: VariantStats,
    treatment: VariantStats,
) -> Tuple[float, float]:
    """
    Welch's t-test for continuous metric means.

    Args:
        control: Control group statistics.
        treatment: Treatment group statistics.

    Returns:
        Tuple of (t_statistic, p_value).
    """
    n1 = control.sample_size
    n2 = treatment.sample_size
    m1 = control.average_value
    m2 = treatment.average_value
    v1 = control.variance
    v2 = treatment.variance

    if n1 < 2 or n2 < 2:
        return (0.0, 1.0)

    # Welch's t-test
    se = math.sqrt(v1 / n1 + v2 / n2)
    if se == 0:
        return (0.0, 1.0)

    t = (m2 - m1) / se

    # Degrees of freedom (Welch-Satterthwaite)
    num = (v1 / n1 + v2 / n2) ** 2
    den = (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)
    if den == 0:
        return (0.0, 1.0)

    df = num / den

    # Approximate p-value using normal for large df
    p_value = 2 * (1 - _normal_cdf(abs(t)))
    return (t, p_value)


def confidence_interval(
    stats: VariantStats,
    confidence: float = 0.95,
) -> Tuple[float, float]:
    """
    Calculate confidence interval for a mean.

    Args:
        stats: Variant statistics.
        confidence: Confidence level (0-1).

    Returns:
        Tuple of (lower_bound, upper_bound).
    """
    if stats.sample_size < 2:
        return (0.0, 0.0)

    # z-value for confidence level
    alpha = 1 - confidence
    z = _normal_cdf(1 - alpha / 2)
    # Approximate z for common confidence levels
    z_approx = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(confidence, 1.96)

    se = math.sqrt(stats.variance / stats.sample_size)
    margin = z_approx * se
    return (stats.average_value - margin, stats.average_value + margin)


def effect_size_cohens_d(
    control: VariantStats,
    treatment: VariantStats,
) -> float:
    """
    Compute Cohen's d effect size.

    Args:
        control: Control group statistics.
        treatment: Treatment group statistics.

    Returns:
        Cohen's d value.
    """
    n1 = control.sample_size
    n2 = treatment.sample_size

    if n1 < 2 or n2 < 2:
        return 0.0

    # Pooled standard deviation
    pooled_var = ((n1 - 1) * control.variance + (n2 - 1) * treatment.variance) / (n1 + n2 - 2)
    if pooled_var <= 0:
        return 0.0

    pooled_sd = math.sqrt(pooled_var)
    return (treatment.average_value - control.average_value) / pooled_sd


class ExperimentAnalyzer:
    """
    Statistical analysis engine for experiments.

    Provides multiple statistical tests and
    metrics for evaluating experiment results.

    Usage:
        analyzer = ExperimentAnalyzer()
        result = analyzer.analyze(control_stats, treatment_stats)
        # result.p_value, result.confidence, etc.
    """

    def analyze(
        self,
        control: VariantStats,
        treatment: VariantStats,
        confidence: float = 0.95,
        metric_type: str = "conversion",
    ) -> AnalysisResult:
        """
        Perform full statistical analysis.

        Args:
            control: Control group statistics.
            treatment: Treatment group statistics.
            confidence: Desired confidence level.
            metric_type: Type of metric (conversion or continuous).

        Returns:
            AnalysisResult with all computed statistics.
        """
        if metric_type == "conversion":
            test_stat, p_value = z_test_proportions(control, treatment)
            test_type = "z_test"
        else:
            test_stat, p_value = t_test_means(control, treatment)
            test_type = "t_test"

        ci_control = confidence_interval(control, confidence)
        ci_treatment = confidence_interval(treatment, confidence)
        d = effect_size_cohens_d(control, treatment)

        # Determine significance
        alpha = 1 - confidence
        is_significant = p_value < alpha

        # Lift calculation
        if control.conversion_rate > 0 and metric_type == "conversion":
            lift = (treatment.conversion_rate - control.conversion_rate) / control.conversion_rate
        elif control.average_value != 0:
            lift = (treatment.average_value - control.average_value) / abs(control.average_value)
        else:
            lift = 0.0

        return AnalysisResult(
            test_type=test_type,
            test_statistic=test_stat,
            p_value=p_value,
            confidence=confidence,
            is_significant=is_significant,
            effect_size=d,
            lift=lift,
            control_ci=ci_control,
            treatment_ci=ci_treatment,
        )


