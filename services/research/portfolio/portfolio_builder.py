"""Portfolio Builder — construct portfolio from alpha pool, strategy output, or custom universe.

Supports construction from:
* Alpha Pool — aggregated alpha signals
* Strategy Output — direct strategy recommendations
* Custom Universe — user-defined asset list
* Existing Portfolio — rebalance from current holdings
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BuildMethod(str, Enum):
    """Portfolio construction methods."""

    ALPHA_POOL = "alpha_pool"
    STRATEGY_OUTPUT = "strategy_output"
    CUSTOM_UNIVERSE = "custom_universe"
    EXISTING_PORTFOLIO = "existing_portfolio"


@dataclass
class BuildResult:
    """Result of portfolio construction."""

    universe: List[str]
    signals: Dict[str, float] = field(default_factory=dict)
    scores: Dict[str, float] = field(default_factory=dict)
    exclusions: List[str] = field(default_factory=list)
    method: BuildMethod = BuildMethod.CUSTOM_UNIVERSE
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "universe": self.universe,
            "num_assets": len(self.universe),
            "signals": self.signals,
            "scores": self.scores,
            "exclusions": self.exclusions,
            "method": self.method.value,
            "metadata": self.metadata,
        }


class PortfolioBuilder:
    """Construct portfolios from various alpha sources.

    Transforms alpha pool signals, strategy outputs, or custom
    universes into actionable portfolio candidates with scores
    and exclusion filtering.
    """

    def __init__(self) -> None:
        self._exclusion_rules: List[Dict[str, Any]] = []

    async def build(
        self,
        alpha_pool: Optional[List[str]] = None,
        universe: Optional[List[str]] = None,
        method: BuildMethod = BuildMethod.CUSTOM_UNIVERSE,
        min_score: float = 0.0,
        max_assets: int = 100,
        **kwargs: Any,
    ) -> BuildResult:
        """Build portfolio candidates from specified source."""

        if method == BuildMethod.ALPHA_POOL and alpha_pool:
            return await self._build_from_alpha_pool(
                alpha_pool, min_score, max_assets, **kwargs
            )
        elif method == BuildMethod.STRATEGY_OUTPUT:
            return await self._build_from_strategy(
                universe or [], **kwargs
            )
        elif method == BuildMethod.CUSTOM_UNIVERSE:
            return await self._build_from_universe(
                universe or [], max_assets, **kwargs
            )
        else:
            # Default: use provided universe
            return await self._build_from_universe(
                universe or alpha_pool or [], max_assets, **kwargs
            )

    async def _build_from_alpha_pool(
        self,
        alpha_pool: List[str],
        min_score: float,
        max_assets: int,
        **kwargs: Any,
    ) -> BuildResult:
        """Build from alpha pool signals with scoring."""
        scores = kwargs.get("scores", {})
        signals = kwargs.get("signals", {})

        # Filter by minimum score
        candidates = {
            asset: score
            for asset, score in scores.items()
            if score >= min_score
        }

        # Sort by score descending
        sorted_candidates = sorted(
            candidates.items(), key=lambda x: x[1], reverse=True
        )

        # Limit to max assets
        selected = sorted_candidates[:max_assets]
        universe = [asset for asset, _ in selected]
        filtered_scores = dict(selected)

        # Apply exclusion rules
        universe = self._apply_exclusions(universe)

        return BuildResult(
            universe=universe,
            signals=signals,
            scores=filtered_scores,
            method=BuildMethod.ALPHA_POOL,
            metadata={"alpha_pool": alpha_pool, "min_score": min_score},
        )

    async def _build_from_strategy(
        self, universe: List[str], **kwargs: Any
    ) -> BuildResult:
        """Build from strategy output recommendations."""
        recommendations = kwargs.get("recommendations", {})
        scores = kwargs.get("scores", {})
        signals = kwargs.get("signals", {})

        # Use strategy recommendations as universe
        if recommendations:
            universe = list(recommendations.keys())

        universe = self._apply_exclusions(universe)

        return BuildResult(
            universe=universe,
            signals=signals,
            scores=scores,
            method=BuildMethod.STRATEGY_OUTPUT,
        )

    async def _build_from_universe(
        self, universe: List[str], max_assets: int, **kwargs: Any
    ) -> BuildResult:
        """Build from custom universe."""
        universe = universe[:max_assets]
        universe = self._apply_exclusions(universe)
        scores = kwargs.get("scores", {})

        return BuildResult(
            universe=universe,
            scores=scores,
            method=BuildMethod.CUSTOM_UNIVERSE,
        )

    def add_exclusion_rule(self, rule: Dict[str, Any]) -> None:
        """Add an exclusion rule (e.g., ST stocks, low liquidity)."""
        self._exclusion_rules.append(rule)

    def _apply_exclusions(self, universe: List[str]) -> List[str]:
        """Apply exclusion rules to filter universe."""
        excluded = set()
        for rule in self._exclusion_rules:
            rule_type = rule.get("type", "")
            if rule_type == "blacklist":
                excluded.update(rule.get("assets", []))
            elif rule_type == "pattern":
                pattern = rule.get("pattern", "")
                excluded.update(
                    a for a in universe if pattern in a
                )
        return [a for a in universe if a not in excluded]
