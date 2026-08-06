"""Exposure Analysis — factor exposure across dimensions.

Supports::

    Sector Exposure, Market Cap Exposure, Style Exposure, Risk Exposure

Measures how factor values correlate with known risk dimensions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExposureResult:
    """Exposure analysis result."""

    factor_name: str = ""
    exposures: Dict[str, float] = field(default_factory=dict)
    sector_exposure: Dict[str, float] = field(default_factory=dict)
    market_cap_exposure: float = 0.0
    style_exposures: Dict[str, float] = field(default_factory=dict)
    risk_exposures: Dict[str, float] = field(default_factory=dict)
    concentration: float = 0.0  # Herfindahl index
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "factor_name": self.factor_name,
            "exposures": self.exposures,
            "sector_exposure": self.sector_exposure,
            "market_cap_exposure": self.market_cap_exposure,
            "style_exposures": self.style_exposures,
            "risk_exposures": self.risk_exposures,
            "concentration": self.concentration,
            "metadata": self.metadata,
        }


class ExposureAnalyzer:
    """Factor exposure analyzer across multiple dimensions.

    Analyzes:
    * Sector/Industry exposure
    * Market cap exposure
    * Style factor exposures (value, momentum, size, quality, vol)
    * Risk factor exposures
    * Concentration (Herfindahl index)
    """

    def __init__(self) -> None:
        pass

    def analyze(
        self,
        factor_values: List[float],
        sectors: Optional[List[str]] = None,
        market_caps: Optional[List[float]] = None,
        style_factors: Optional[Dict[str, List[float]]] = None,
        risk_factors: Optional[Dict[str, List[float]]] = None,
        factor_name: str = "",
    ) -> ExposureResult:
        """Analyze factor exposures across dimensions.

        Args:
            factor_values: factor values
            sectors: sector/industry codes
            market_caps: log market cap values
            style_factors: style factor exposures
            risk_factors: risk factor exposures
            factor_name: factor identifier

        Returns:
            ExposureResult with exposure metrics
        """
        result = ExposureResult(factor_name=factor_name)

        if not factor_values:
            return result

        n = len(factor_values)

        # Sector exposure
        if sectors and len(sectors) == n:
            result.sector_exposure = self._sector_exposure(factor_values, sectors)

        # Market cap exposure
        if market_caps and len(market_caps) == n:
            result.market_cap_exposure = self._correlation(factor_values, market_caps)

        # Style factor exposures
        if style_factors:
            for style_name, style_vals in style_factors.items():
                if len(style_vals) == n:
                    result.style_exposures[style_name] = self._correlation(
                        factor_values, style_vals
                    )

        # Risk factor exposures
        if risk_factors:
            for risk_name, risk_vals in risk_factors.items():
                if len(risk_vals) == n:
                    result.risk_exposures[risk_name] = self._correlation(
                        factor_values, risk_vals
                    )

        # Combine all exposures
        result.exposures = {
            "market_cap": result.market_cap_exposure,
            **result.style_exposures,
            **result.risk_exposures,
        }

        # Concentration (Herfindahl index of exposures)
        all_exposures = list(result.exposures.values())
        if all_exposures:
            result.concentration = sum(e ** 2 for e in all_exposures)

        return result

    def _correlation(
        self, a: List[float], b: List[float]
    ) -> float:
        """Compute Pearson correlation."""
        n = min(len(a), len(b))
        if n < 2:
            return 0.0

        mean_a = sum(a[:n]) / n
        mean_b = sum(b[:n]) / n
        cov = sum((ai - mean_a) * (bi - mean_b) for ai, bi in zip(a[:n], b[:n]))
        var_a = sum((ai - mean_a) ** 2 for ai in a[:n])
        var_b = sum((bi - mean_b) ** 2 for bi in b[:n])

        if var_a == 0 or var_b == 0:
            return 0.0

        return cov / ((var_a * var_b) ** 0.5)

    def _sector_exposure(
        self,
        factor_values: List[float],
        sectors: List[str],
    ) -> Dict[str, float]:
        """Compute average factor value per sector."""
        sector_sums: Dict[str, float] = {}
        sector_counts: Dict[str, int] = {}

        for val, sec in zip(factor_values, sectors):
            sector_sums[sec] = sector_sums.get(sec, 0.0) + val
            sector_counts[sec] = sector_counts.get(sec, 0) + 1

        return {
            sec: sector_sums[sec] / sector_counts[sec]
            for sec in sector_sums
            if sector_counts[sec] > 0
        }

    def exposure_summary(self, result: ExposureResult) -> Dict[str, Any]:
        """Generate a human-readable exposure summary."""
        max_exposure = max(
            abs(v) for v in result.exposures.values()
        ) if result.exposures else 0.0

        return {
            "factor_name": result.factor_name,
            "max_exposure": max_exposure,
            "market_cap_bias": abs(result.market_cap_exposure),
            "top_sectors": sorted(
                result.sector_exposure.items(),
                key=lambda x: abs(x[1]),
                reverse=True,
            )[:5],
            "concentration": result.concentration,
            "is_neutral": max_exposure < 0.1,
        }
