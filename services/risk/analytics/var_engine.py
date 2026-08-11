"""
VaR Engine — Unified Value-at-Risk calculation engine.

Provides a common interface for computing VaR using multiple methodologies:
Historical, Parametric (Variance-Covariance), and Monte Carlo simulation.

Supports multiple confidence levels (95%, 99%, etc.) and time horizons.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .historical_var import HistoricalVaR
from .parametric_var import ParametricVaR
from .montecarlo_var import MonteCarloVaR

logger = logging.getLogger(__name__)


@dataclass
class VaRConfig:
    """Configuration for VaR calculations."""
    confidence_levels: list[float] = field(default_factory=lambda: [0.95, 0.975, 0.99])
    time_horizons_days: list[int] = field(default_factory=lambda: [1, 5, 10, 20])
    historical_window_days: int = 500
    decay_factor: float = 0.94  # for EWMA
    montecarlo_paths: int = 100_000
    montecarlo_steps: int = 252
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VaRResult:
    """Result of VaR calculations."""
    method: str  # historical, parametric, montecarlo
    confidence_level: float
    time_horizon_days: int
    var_value: float
    var_percentage: float
    portfolio_value: float
    calculation_time_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


class VaREngine:
    """
    Unified Value-at-Risk calculation engine.

    Supports three methodologies:
    - Historical VaR: Non-parametric, uses historical return distribution
    - Parametric VaR: Assumes normal distribution with variance-covariance
    - Monte Carlo VaR: Simulates paths using stochastic models

    Usage::

        engine = VaREngine(config=VaRConfig())
        await engine.initialize()
        results = await engine.calculate_var(portfolio_data, method="all")
    """

    def __init__(self, config: Optional[VaRConfig] = None) -> None:
        self._config = config or VaRConfig()
        self._historical = HistoricalVaR()
        self._parametric = ParametricVaR()
        self._montecarlo = MonteCarloVaR()
        self._initialized = False

    @property
    def config(self) -> VaRConfig:
        return self._config

    async def initialize(self) -> None:
        """Initialize all VaR calculators."""
        if self._initialized:
            return
        await asyncio.gather(
            self._historical.initialize(),
            self._parametric.initialize(),
            self._montecarlo.initialize(),
        )
        self._initialized = True
        logger.info("VaREngine initialized.")

    async def calculate_var(
        self,
        portfolio_data: dict[str, Any],
        method: str = "all",
        confidence_level: Optional[float] = None,
        horizon_days: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Calculate Value-at-Risk.

        Parameters
        ----------
        portfolio_data : dict
            Portfolio snapshot with positions and historical returns.
        method : str
            One of: "historical", "parametric", "montecarlo", "all".
        confidence_level : float, optional
            Override default confidence level.
        horizon_days : int, optional
            Override default time horizon.

        Returns
        -------
        dict
            VaR results per method.
        """
        import time

        if not self._initialized:
            await self.initialize()

        conf_levels = [confidence_level] if confidence_level else self._config.confidence_levels
        horizons = [horizon_days] if horizon_days else self._config.time_horizons_days

        results: dict[str, Any] = {"portfolio_value": portfolio_data.get("total_value", 0)}
        t_start = time.perf_counter()

        tasks = {}

        if method in ("historical", "all"):
            tasks["historical"] = asyncio.create_task(
                self._historical.calculate(portfolio_data, conf_levels, horizons)
            )

        if method in ("parametric", "all"):
            tasks["parametric"] = asyncio.create_task(
                self._parametric.calculate(portfolio_data, conf_levels, horizons)
            )

        if method in ("montecarlo", "all"):
            tasks["montecarlo"] = asyncio.create_task(
                self._montecarlo.calculate(portfolio_data, conf_levels, horizons)
            )

        for name, task in tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"VaR calculation ({name}) failed: {e}")
                results[name] = {"error": str(e)}

        results["calculation_time_ms"] = (time.perf_counter() - t_start) * 1000
        return results

    # ---- Convenience Methods ----

    async def historical_var(
        self,
        portfolio_data: dict[str, Any],
        confidence: float = 0.95,
        horizon: int = 1,
    ) -> VaRResult:
        """Calculate Historical VaR."""
        result = await self._historical.calculate(portfolio_data, [confidence], [horizon])
        var_entries = result.get("var_entries", [])
        if var_entries:
            e = var_entries[0]
            return VaRResult(
                method="historical",
                confidence_level=confidence,
                time_horizon_days=horizon,
                var_value=e["var_value"],
                var_percentage=e["var_percentage"],
                portfolio_value=e["portfolio_value"],
                calculation_time_ms=result.get("calculation_time_ms", 0),
            )
        return VaRResult("historical", confidence, horizon, 0, 0, 0, 0)

    async def parametric_var(
        self,
        portfolio_data: dict[str, Any],
        confidence: float = 0.95,
        horizon: int = 1,
    ) -> VaRResult:
        """Calculate Parametric VaR."""
        result = await self._parametric.calculate(portfolio_data, [confidence], [horizon])
        var_entries = result.get("var_entries", [])
        if var_entries:
            e = var_entries[0]
            return VaRResult(
                method="parametric",
                confidence_level=confidence,
                time_horizon_days=horizon,
                var_value=e["var_value"],
                var_percentage=e["var_percentage"],
                portfolio_value=e["portfolio_value"],
                calculation_time_ms=result.get("calculation_time_ms", 0),
            )
        return VaRResult("parametric", confidence, horizon, 0, 0, 0, 0)

    async def montecarlo_var(
        self,
        portfolio_data: dict[str, Any],
        confidence: float = 0.95,
        horizon: int = 1,
    ) -> VaRResult:
        """Calculate Monte Carlo VaR."""
        result = await self._montecarlo.calculate(portfolio_data, [confidence], [horizon])
        var_entries = result.get("var_entries", [])
        if var_entries:
            e = var_entries[0]
            return VaRResult(
                method="montecarlo",
                confidence_level=confidence,
                time_horizon_days=horizon,
                var_value=e["var_value"],
                var_percentage=e["var_percentage"],
                portfolio_value=e["portfolio_value"],
                calculation_time_ms=result.get("calculation_time_ms", 0),
            )
        return VaRResult("montecarlo", confidence, horizon, 0, 0, 0, 0)
