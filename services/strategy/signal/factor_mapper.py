"""
Factor Mapper — Research factor → Alpha factor mapping.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Bridges Commit 11 Research Platform with the Alpha Engine by:
    - Mapping research factor names to alpha-expected factor names
    - Handling factor transformations (log, diff, rank)
    - Managing factor version compatibility
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FactorMapper:
    """Maps raw research factors to alpha-ready factor inputs.

    Research platforms may output factors with different naming conventions,
    frequencies, or transformations than what alpha models expect. This
    mapper normalizes the interface.
    """

    def __init__(self):
        # factor_name → (transform_fn, params)
        self._transforms: Dict[str, Tuple[str, Dict[str, Any]]] = {}

        # Name mappings: research_name → alpha_name
        self._name_map: Dict[str, str] = {}

        # Register built-in transforms
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register common factor transformations."""
        # Standard name mappings
        common_mappings = {
            "momentum_1m": "momentum_1m",
            "momentum_3m": "momentum_3m",
            "momentum_6m": "momentum_6m",
            "momentum_12m": "momentum_12m",
            "pe_ratio": "pe_ratio",
            "pb_ratio": "pb_ratio",
            "ps_ratio": "ps_ratio",
            "roe": "roe",
            "roa": "roa",
            "profit_margin": "profit_margin",
            "debt_ratio": "debt_ratio",
            "dividend_yield": "dividend_yield",
            "realized_vol": "realized_vol",
            "implied_vol": "implied_vol",
            "beta": "beta",
            "market_cap": "market_cap",
            "volume": "volume",
        }
        self._name_map.update(common_mappings)

    # ------------------------------------------------------------------
    # Factor Mapping
    # ------------------------------------------------------------------

    async def map_factors(
        self,
        raw_factors: Dict[str, Dict[str, float]],
        instruments: List[str],
    ) -> Dict[str, Dict[str, float]]:
        """Map raw research factors to alpha-compatible factor values.

        Args:
            raw_factors: {factor_name: {instrument: value}} from research platform.
            instruments: List of instruments to map factors for.

        Returns:
            Mapped factors with standardized names and transformations applied.
        """
        mapped: Dict[str, Dict[str, float]] = {}

        for factor_name, instrument_values in raw_factors.items():
            # Resolve name mapping
            target_name = self._name_map.get(factor_name, factor_name)

            # Apply transformation if registered
            transform = self._transforms.get(factor_name)
            if transform:
                transform_fn_name, params = transform
                transformed = await self._apply_transform(
                    transform_fn_name, instrument_values, params,
                )
                mapped[target_name] = transformed
            else:
                # Pass through as-is
                mapped[target_name] = dict(instrument_values)

        # Ensure all instruments have entries (fill NaN with None)
        for factor_data in mapped.values():
            for inst in instruments:
                if inst not in factor_data:
                    factor_data[inst] = None

        return mapped

    # ------------------------------------------------------------------
    # Transformations
    # ------------------------------------------------------------------

    async def _apply_transform(
        self,
        transform_name: str,
        values: Dict[str, float],
        params: Dict[str, Any],
    ) -> Dict[str, float]:
        """Apply a named transformation to factor values."""
        result = {}

        for inst, value in values.items():
            if value is None or (isinstance(value, float) and math.isnan(value)):
                result[inst] = None
                continue

            try:
                if transform_name == "log":
                    result[inst] = math.log(max(value, 1e-10))
                elif transform_name == "rank":
                    result[inst] = value  # Cross-sectional ranking done elsewhere
                elif transform_name == "diff":
                    result[inst] = value  # Time-series diff done elsewhere
                elif transform_name == "zscore":
                    result[inst] = value  # Normalization done in pipeline
                elif transform_name == "winsorize":
                    clip = params.get("clip", 3.0)
                    result[inst] = max(-clip, min(clip, value))
                elif transform_name == "sigmoid":
                    try:
                        result[inst] = 1.0 / (1.0 + math.exp(-value))
                    except OverflowError:
                        result[inst] = 1.0 if value > 0 else 0.0
                else:
                    result[inst] = value
            except (ValueError, OverflowError):
                result[inst] = None

        return result

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def add_mapping(self, research_name: str, alpha_name: str) -> None:
        """Add a name mapping from research factor to alpha factor."""
        self._name_map[research_name] = alpha_name

    def add_transform(self, factor_name: str, transform: str, **params) -> None:
        """Register a transformation for a factor."""
        self._transforms[factor_name] = (transform, params)

    def list_mappings(self) -> Dict[str, str]:
        return dict(self._name_map)
