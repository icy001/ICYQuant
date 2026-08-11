"""
Liquidity Simulator — Monte Carlo simulation of liquidity scenarios.

Simulates thousands of liquidity paths to quantify:
- Worst-case transaction costs
- Liquidation horizon under stress
- Capacity survivability probabilities
"""

from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from .liquidity_profile import LiquidityProfile
from .liquidity_scenario import LiquidityScenario, ScenarioResult, ScenarioType
from .liquidity_regime import LiquidityRegimeDetector


@dataclass
class SimulationParams:
    """Parameters for a liquidity simulation run."""

    num_simulations: int = 1000
    horizon_days: int = 20
    confidence_level: float = 0.95
    seed: Optional[int] = None

    # Stochastic parameters
    volume_volatility: float = 0.15      # daily vol of volume
    spread_volatility: float = 0.10       # daily vol of spread
    volatility_volatility: float = 0.30    # vol of vol
    depth_volatility: float = 0.12

    # Mean reversion
    volume_mean_reversion: float = 0.1
    spread_mean_reversion: float = 0.15
    depth_mean_reversion: float = 0.1

    # Scenario injection
    scenario_day: Optional[int] = None    # day to inject shock (None = random)
    scenario_probability: float = 0.1     # probability of shock on any given day

    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_simulations": self.num_simulations,
            "horizon_days": self.horizon_days,
            "confidence_level": self.confidence_level,
            "volume_volatility": self.volume_volatility,
            "spread_volatility": self.spread_volatility,
            "volatility_volatility": self.volatility_volatility,
            "scenario_probability": self.scenario_probability,
        }


@dataclass
class SimulationPath:
    """A single simulated liquidity path."""

    path_id: str = field(default_factory=lambda: f"SP-{uuid.uuid4().hex[:8]}")
    asset: str = ""
    day_values: List[Dict[str, float]] = field(default_factory=list)

    # End-of-path aggregated metrics
    final_volume: float = 0.0
    final_spread_bps: float = 0.0
    final_volatility: float = 0.0
    final_liquidity_score: float = 0.0

    # Path-level metrics
    min_liquidity_score: float = 100.0
    max_spread_bps: float = 0.0
    regime_shifts: int = 0
    crisis_days: int = 0
    shock_encountered: bool = False

    # Capacity impact
    total_daily_capacity: float = 0.0
    min_daily_capacity: float = float("inf")
    liquidation_days: float = 0.0


@dataclass
class SimulationResult:
    """Aggregated results from a simulation run."""

    result_id: str = field(default_factory=lambda: f"LSIM-{uuid.uuid4().hex[:8]}")
    params: SimulationParams = field(default_factory=SimulationParams)
    paths: List[SimulationPath] = field(default_factory=list)

    # Distribution statistics
    mean_final_score: float = 0.0
    median_final_score: float = 0.0
    var_95_score: float = 0.0
    var_99_score: float = 0.0

    mean_final_volume: float = 0.0
    var_95_volume: float = 0.0

    mean_max_spread: float = 0.0
    var_95_spread: float = 0.0

    # Capacity risk metrics
    mean_liquidation_days: float = 0.0
    var_95_liquidation_days: float = 0.0
    probability_capacity_collapse: float = 0.0
    probability_regime_shift: float = 0.0
    probability_crisis: float = 0.0

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "params": self.params.to_dict(),
            "path_count": len(self.paths),
            "mean_final_score": round(self.mean_final_score, 2),
            "var_95_score": round(self.var_95_score, 2),
            "var_99_score": round(self.var_99_score, 2),
            "mean_final_volume": round(self.mean_final_volume, 2),
            "mean_max_spread": round(self.mean_max_spread, 2),
            "mean_liquidation_days": round(self.mean_liquidation_days, 1),
            "var_95_liquidation_days": round(self.var_95_liquidation_days, 1),
            "probability_capacity_collapse": round(self.probability_capacity_collapse, 4),
            "probability_regime_shift": round(self.probability_regime_shift, 4),
            "probability_crisis": round(self.probability_crisis, 4),
        }


class LiquiditySimulator:
    """Monte Carlo simulation of liquidity paths for capacity risk assessment."""

    def __init__(self):
        self._regime_detector = LiquidityRegimeDetector()
        self._scenarios: List[LiquidityScenario] = []
        self._rng: Optional[random.Random] = None

    def add_scenario(self, scenario: LiquidityScenario) -> None:
        """Register a shock scenario for injection during simulation."""
        self._scenarios.append(scenario)

    def simulate(self,
                 profile: LiquidityProfile,
                 params: Optional[SimulationParams] = None) -> SimulationResult:
        """Run Monte Carlo simulation of liquidity paths."""

        if params is None:
            params = SimulationParams()

        if params.seed is not None:
            self._rng = random.Random(params.seed)
        else:
            self._rng = random.Random()

        paths: List[SimulationPath] = []

        for _ in range(params.num_simulations):
            path = self._simulate_single_path(profile, params)
            paths.append(path)

        result = self._aggregate_results(paths, params)
        return result

    def _simulate_single_path(self,
                               profile: LiquidityProfile,
                               params: SimulationParams) -> SimulationPath:
        """Simulate one liquidity path over the horizon."""
        path = SimulationPath(asset=profile.asset)

        vol = profile.avg_daily_volume
        spread = profile.spread_bps
        volatility = profile.volatility
        depth = profile.depth

        min_score = 100.0
        max_spread = spread
        regime_shifts = 0
        crisis_days = 0
        shock_encountered = False
        total_capacity = 0.0
        min_capacity = float("inf")
        prev_regime = "NORMAL"

        for day in range(params.horizon_days):
            # Check for shock injection
            if params.scenario_day is not None and day == params.scenario_day:
                shock_encountered = True
                vol, spread, volatility, depth = self._apply_random_scenario(
                    vol, spread, volatility, depth, profile
                )
            elif self._rng.random() < params.scenario_probability:
                shock_encountered = True
                vol, spread, volatility, depth = self._apply_random_scenario(
                    vol, spread, volatility, depth, profile
                )

            # Stochastic evolution with mean reversion
            vol *= math.exp(self._rng.gauss(
                params.volume_mean_reversion * math.log(profile.avg_daily_volume / max(vol, 1)),
                params.volume_volatility,
            ))
            spread *= math.exp(self._rng.gauss(
                params.spread_mean_reversion * math.log(profile.spread_bps / max(spread, 0.01)),
                params.spread_volatility,
            ))
            depth *= math.exp(self._rng.gauss(
                params.depth_mean_reversion * math.log(profile.depth / max(depth, 1)),
                params.depth_volatility,
            ))
            volatility *= math.exp(self._rng.gauss(0, params.volatility_volatility))

            # Clamp to realistic ranges
            vol = max(profile.avg_daily_volume * 0.01, vol)
            spread = max(0.5, spread)
            volatility = max(0.05, volatility)
            depth = max(1.0, depth)

            # Compute daily metrics
            score = self._compute_daily_score(vol, spread, depth, volatility, profile)
            regime = self._classify_regime(score)
            daily_cap = vol * self._participation_limit_by_regime(regime)

            # Track extremes
            min_score = min(min_score, score)
            max_spread = max(max_spread, spread)
            min_capacity = min(min_capacity, daily_cap)
            total_capacity += daily_cap

            if regime != prev_regime:
                regime_shifts += 1
                prev_regime = regime
            if regime in ("STRESSED", "CRISIS"):
                crisis_days += 1

            # Store day values
            path.day_values.append({
                "day": day,
                "volume": vol,
                "spread_bps": spread,
                "volatility": volatility,
                "depth": depth,
                "liquidity_score": score,
                "regime": regime,
                "daily_capacity": daily_cap,
            })

        # Finalize path
        path.final_volume = vol
        path.final_spread_bps = spread
        path.final_volatility = volatility
        path.final_liquidity_score = self._compute_daily_score(
            vol, spread, depth, volatility, profile
        )
        path.min_liquidity_score = min_score
        path.max_spread_bps = max_spread
        path.regime_shifts = regime_shifts
        path.crisis_days = crisis_days
        path.shock_encountered = shock_encountered
        path.total_daily_capacity = total_capacity
        path.min_daily_capacity = min_capacity

        # Estimate liquidation days for a position of 10% ADV
        position = profile.avg_daily_volume * 0.1
        avg_capacity = total_capacity / params.horizon_days if params.horizon_days > 0 else 0
        path.liquidation_days = position / avg_capacity if avg_capacity > 0 else float("inf")

        return path

    def _apply_random_scenario(self,
                                 vol: float, spread: float, vola: float, depth: float,
                                 base_profile: LiquidityProfile) -> Tuple[float, ...]:
        """Apply a random registered scenario."""
        if not self._scenarios:
            # Default shock if no scenarios registered
            return (
                vol * 0.5,
                spread * 3.0,
                vola * 2.0,
                depth * 0.3,
            )

        scenario = self._rng.choice(self._scenarios)
        return (
            vol * scenario.volume_multiplier,
            spread * scenario.spread_multiplier,
            vola * scenario.volatility_multiplier,
            depth * scenario.depth_multiplier,
        )

    # ── Aggregation ───────────────────────────────────────────────

    def _aggregate_results(self,
                            paths: List[SimulationPath],
                            params: SimulationParams) -> SimulationResult:
        """Compute statistics across all simulation paths."""
        result = SimulationResult(params=params, paths=paths)

        # Sort scores for VaR
        def _percentile(values: List[float], p: float) -> float:
            if not values:
                return 0.0
            sorted_vals = sorted(values)
            idx = int(len(sorted_vals) * p)
            return sorted_vals[idx]

        final_scores = [p.final_liquidity_score for p in paths]
        final_volumes = [p.final_volume for p in paths]
        max_spreads = [p.max_spread_bps for p in paths]
        liq_days = [min(p.liquidation_days, 999) for p in paths]

        result.mean_final_score = sum(final_scores) / len(final_scores)
        result.median_final_score = _percentile(final_scores, 0.5)
        result.var_95_score = _percentile(final_scores, 0.95)
        result.var_99_score = _percentile(final_scores, 0.99)

        result.mean_final_volume = sum(final_volumes) / len(final_volumes)
        result.var_95_volume = _percentile(final_volumes, 0.95)

        result.mean_max_spread = sum(max_spreads) / len(max_spreads)
        result.var_95_spread = _percentile(max_spreads, 0.95)

        result.mean_liquidation_days = sum(liq_days) / len(liq_days)
        result.var_95_liquidation_days = _percentile(liq_days, 0.95)

        result.probability_capacity_collapse = sum(
            1 for p in paths if p.min_daily_capacity <= p.final_volume * 0.01
        ) / len(paths)

        result.probability_regime_shift = sum(
            1 for p in paths if p.regime_shifts > 0
        ) / len(paths)

        result.probability_crisis = sum(
            1 for p in paths if p.crisis_days > 0
        ) / len(paths)

        return result

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _compute_daily_score(vol: float, spread: float, depth: float,
                              volatility: float, base: LiquidityProfile) -> float:
        volume_score = min(30, 30 * vol / max(base.avg_daily_volume, 1))
        spread_score = min(25, 25 * base.spread_bps / max(spread, 0.01)) if spread > 0 else 25
        depth_score = min(20, 20 * depth / max(base.depth, 1))
        vol_penalty = max(0, 15 * (volatility / max(base.volatility, 0.01) - 1))
        return max(0, volume_score + spread_score + depth_score + 15 - vol_penalty)

    @staticmethod
    def _classify_regime(score: float) -> str:
        if score >= 70:
            return "NORMAL"
        elif score >= 50:
            return "LOW_LIQUIDITY"
        elif score >= 30:
            return "STRESSED"
        return "CRISIS"

    @staticmethod
    def _participation_limit_by_regime(regime: str) -> float:
        return {
            "NORMAL": 0.10,
            "HIGH_LIQUIDITY": 0.15,
            "LOW_LIQUIDITY": 0.05,
            "STRESSED": 0.02,
            "CRISIS": 0.01,
        }.get(regime, 0.05)

    def summary(self) -> Dict[str, Any]:
        return {
            "scenarios_registered": len(self._scenarios),
            "scenario_names": [s.name for s in self._scenarios],
        }
