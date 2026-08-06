"""Neutralization — remove systematic biases from factor values.

Supports::

    Industry Neutralization, Market Cap Neutralization,
    Style Neutralization, Custom Neutralization

Reduces systematic biases to isolate pure alpha signal.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NeutralizationMethod(str, Enum):
    """Neutralization targets."""

    INDUSTRY = "industry"
    MARKET_CAP = "market_cap"
    STYLE = "style"
    CUSTOM = "custom"


class Neutralizer:
    """Systematic bias neutralization for factor values.

    Methods:
    * Industry Neutralization: regress out industry dummy effects
    * Market Cap Neutralization: regress out log market cap
    * Style Neutralization: regress out style factor exposures
    * Custom Neutralization: regress out arbitrary custom variables

    All methods use residual regression: factor_residual = factor - predicted(factor | controls)
    """

    def __init__(self) -> None:
        self._neutralizations_applied: int = 0

    @property
    def neutralizations_applied(self) -> int:
        return self._neutralizations_applied

    def neutralize(
        self,
        factor_values: List[float],
        targets: List[NeutralizationMethod],
        controls: Optional[Dict[str, List[float]]] = None,
    ) -> List[float]:
        """Neutralize factor values against specified targets.

        Args:
            factor_values: raw factor values
            targets: list of neutralization targets
            controls: auxiliary data for neutralization
                      (e.g., industry dummies, market caps, style scores)

        Returns:
            neutralized factor values (residuals)
        """
        if not factor_values:
            return []

        result = list(factor_values)

        for target in targets:
            if target == NeutralizationMethod.INDUSTRY:
                result = self._neutralize_industry(result, controls)
            elif target == NeutralizationMethod.MARKET_CAP:
                result = self._neutralize_market_cap(result, controls)
            elif target == NeutralizationMethod.STYLE:
                result = self._neutralize_style(result, controls)
            elif target == NeutralizationMethod.CUSTOM:
                result = self._neutralize_custom(result, controls)

        self._neutralizations_applied += 1
        return result

    def _neutralize_industry(
        self,
        values: List[float],
        controls: Optional[Dict[str, List[float]]],
    ) -> List[float]:
        """Remove industry effects via residual regression."""
        if controls is None or "industry" not in controls:
            logger.warning("Industry neutralization skipped: no industry data")
            return values

        industries = controls["industry"]
        if len(industries) != len(values):
            return values

        # Group by industry, compute mean, subtract
        industry_means: Dict[Any, float] = {}
        industry_counts: Dict[Any, int] = {}
        for v, ind in zip(values, industries):
            industry_means[ind] = industry_means.get(ind, 0.0) + v
            industry_counts[ind] = industry_counts.get(ind, 0) + 1

        for ind in industry_means:
            industry_means[ind] /= industry_counts[ind]

        return [v - industry_means.get(ind, 0.0) for v, ind in zip(values, industries)]

    def _neutralize_market_cap(
        self,
        values: List[float],
        controls: Optional[Dict[str, List[float]]],
    ) -> List[float]:
        """Remove market cap effects via residual regression."""
        if controls is None or "market_cap" not in controls:
            logger.warning("Market cap neutralization skipped: no data")
            return values

        caps = controls["market_cap"]
        if len(caps) != len(values):
            return values

        # Simple linear regression: values = alpha + beta * log(cap) + residual
        import math
        log_caps = [math.log(max(c, 1e-10)) for c in caps]

        n = len(values)
        mean_x = sum(log_caps) / n
        mean_y = sum(values) / n

        cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(log_caps, values))
        var_x = sum((x - mean_x) ** 2 for x in log_caps)

        if var_x == 0:
            return values

        beta = cov / var_x
        alpha = mean_y - beta * mean_x

        return [y - (alpha + beta * x) for y, x in zip(values, log_caps)]

    def _neutralize_style(
        self,
        values: List[float],
        controls: Optional[Dict[str, List[float]]],
    ) -> List[float]:
        """Remove style factor effects."""
        if controls is None:
            logger.warning("Style neutralization skipped: no data")
            return values

        result = list(values)
        for style_name, style_values in controls.items():
            if style_name == "industry" or style_name == "market_cap":
                continue
            if len(style_values) != len(values):
                continue

            # Simple univariate regression for each style
            n = len(values)
            mean_x = sum(style_values) / n
            mean_y = sum(result) / n
            cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(style_values, result))
            var_x = sum((x - mean_x) ** 2 for x in style_values)

            if var_x == 0:
                continue

            beta = cov / var_x
            alpha = mean_y - beta * mean_x
            result = [y - (alpha + beta * x) for y, x in zip(result, style_values)]

        return result

    def _neutralize_custom(
        self,
        values: List[float],
        controls: Optional[Dict[str, List[float]]],
    ) -> List[float]:
        """Remove custom variable effects."""
        if controls is None:
            logger.warning("Custom neutralization skipped: no data")
            return values

        result = list(values)
        for var_name, var_values in controls.items():
            if var_name in ("industry", "market_cap"):
                continue
            if len(var_values) != len(values):
                continue

            n = len(values)
            mean_x = sum(var_values) / n
            mean_y = sum(result) / n
            cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(var_values, result))
            var_x = sum((x - mean_x) ** 2 for x in var_values)

            if var_x == 0:
                continue

            beta = cov / var_x
            alpha = mean_y - beta * mean_x
            result = [y - (alpha + beta * x) for y, x in zip(result, var_values)]

        return result

    def exposure_check(
        self,
        factor_values: List[float],
        exposures: Dict[str, List[float]],
    ) -> Dict[str, float]:
        """Check remaining exposure after neutralization."""
        results: Dict[str, float] = {}
        for name, exp_values in exposures.items():
            if len(exp_values) != len(factor_values):
                continue
            n = len(factor_values)
            mean_f = sum(factor_values) / n
            mean_e = sum(exp_values) / n
            cov = sum((f - mean_f) * (e - mean_e) for f, e in zip(factor_values, exp_values))
            var_f = sum((f - mean_f) ** 2 for f in factor_values)
            var_e = sum((e - mean_e) ** 2 for e in exp_values)
            if var_f > 0 and var_e > 0:
                corr = cov / ((var_f * var_e) ** 0.5)
                results[name] = corr
        return results
