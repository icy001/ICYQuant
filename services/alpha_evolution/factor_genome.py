"""
Factor Genome — Specialized genome for factor expressions.

A Factor Genome encodes a factor expression with:
    - Feature inputs
    - Operators (arithmetic, comparison)
    - Transformation functions (momentum, zscore, rank, etc.)
    - Window/lookback parameters
    - Normalization and neutralization settings

Factor Genome structure example:
    rank(zscore(momentum(close, 20) * volume_ratio(10)))
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from services.alpha_evolution.genome import (
    ExpressionType,
    Genome,
    GenomeType,
)
from services.alpha_evolution.gene import (
    Gene,
    GeneFunction,
    GeneOperator,
    GeneType,
)


class FactorCategory(Enum):
    """Categories of factor types."""

    MOMENTUM = "momentum"
    VALUE = "value"
    QUALITY = "quality"
    VOLATILITY = "volatility"
    LIQUIDITY = "liquidity"
    VOLUME = "volume"
    GROWTH = "growth"
    SENTIMENT = "sentiment"
    EVENT = "event"
    CROSS_SECTIONAL = "cross_sectional"
    TIME_SERIES = "time_series"
    ALTERNATIVE = "alternative"
    COMPOSITE = "composite"
    UNKNOWN = "unknown"


# Feature taxonomy for factor construction
FEATURE_TAXONOMY: Dict[str, List[str]] = {
    "price": ["open", "high", "low", "close", "vwap", "adjusted_close"],
    "volume": ["volume", "turnover", "dollar_volume", "volume_ratio", "adv"],
    "returns": ["return_1d", "return_5d", "return_20d", "log_return_1d"],
    "volatility": ["realized_vol_20d", "realized_vol_60d", "parkinson_vol", "garman_klass_vol"],
    "momentum": ["momentum_20d", "momentum_60d", "momentum_120d", "rsi_14d"],
    "value": ["pe_ratio", "pb_ratio", "ps_ratio", "ev_ebitda", "dividend_yield"],
    "quality": ["roe", "roa", "gross_margin", "debt_to_equity", "current_ratio"],
    "growth": ["revenue_growth_yoy", "earnings_growth_yoy", "fcf_growth"],
    "liquidity": ["bid_ask_spread", "amihud_illiquidity", "market_cap"],
    "sentiment": ["short_interest", "analyst_rating", "news_sentiment"],
}


class FactorGenome:
    """
    Factory and utilities for factor-specific genomes.

    Provides:
        - Factor genome construction templates
        - Category-based factor generation
        - Factor-specific mutation operations
        - Factor expression validation
    """

    # ── Factory Methods ────────────────────────────────────

    @staticmethod
    def create_empty() -> Genome:
        """Create an empty factor genome."""
        return Genome(
            genome_type=GenomeType.FACTOR,
            name="empty_factor",
            creation_method="seed",
        )

    @staticmethod
    def create_momentum(
        feature: str = "close",
        window: int = 20,
    ) -> Genome:
        """Create a simple momentum factor genome."""
        genome = Genome(
            genome_type=GenomeType.FACTOR,
            name=f"momentum_{feature}_{window}",
            expression_type=ExpressionType.RANK,
            parameters={"feature": feature, "window": window},
            creation_method="seed",
        )
        genome.root_gene = Gene.momentum(feature, window)
        return genome

    @staticmethod
    def create_volatility(
        feature: str = "close",
        window: int = 20,
    ) -> Genome:
        """Create a volatility factor genome."""
        genome = Genome(
            genome_type=GenomeType.FACTOR,
            name=f"volatility_{feature}_{window}",
            expression_type=ExpressionType.RANK,
            parameters={"feature": feature, "window": window},
        )
        genome.root_gene = Gene.volatility(feature, window)
        return genome

    @staticmethod
    def create_zscore_momentum(
        feature: str = "close",
        momentum_window: int = 20,
        zscore_window: int = 252,
    ) -> Genome:
        """Create a z-score normalized momentum factor."""
        genome = Genome(
            genome_type=GenomeType.FACTOR,
            name=f"zscore_momentum_{feature}_{momentum_window}",
            expression_type=ExpressionType.RANK,
            parameters={
                "feature": feature,
                "momentum_window": momentum_window,
                "zscore_window": zscore_window,
            },
        )
        momentum_gene = Gene.momentum(feature, momentum_window)
        genome.root_gene = Gene.zscore(momentum_gene, zscore_window)
        return genome

    @staticmethod
    def create_composite_factor(
        factors: List[tuple[Gene, float]],
        name: str = "composite",
    ) -> Genome:
        """Create a weighted composite factor genome."""
        genome = Genome(
            genome_type=GenomeType.FACTOR,
            name=name,
            expression_type=ExpressionType.RANK,
            creation_method="seed",
        )
        genome.root_gene = Gene.composite(*factors)
        return genome

    @staticmethod
    def create_volume_weighted(
        feature: str = "close",
        momentum_window: int = 20,
        volume_window: int = 10,
    ) -> Genome:
        """Create a volume-weighted momentum factor."""
        genome = Genome(
            genome_type=GenomeType.FACTOR,
            name=f"vol_weighted_momentum_{feature}",
            expression_type=ExpressionType.RANK,
            parameters={
                "feature": feature,
                "momentum_window": momentum_window,
                "volume_window": volume_window,
            },
        )
        momentum_gene = Gene.momentum(feature, momentum_window)
        volume_gene = Gene.function(
            GeneFunction.VOLUME_RATIO,
            Gene.operand("volume"),
            window=volume_window,
        )
        genome.root_gene = Gene.operator(
            GeneOperator.MUL, momentum_gene, volume_gene
        )
        return genome

    @staticmethod
    def from_template(
        template_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Genome]:
        """Create a factor genome from a named template."""
        params = params or {}
        templates = {
            "momentum": lambda: FactorGenome.create_momentum(
                params.get("feature", "close"),
                params.get("window", 20),
            ),
            "volatility": lambda: FactorGenome.create_volatility(
                params.get("feature", "close"),
                params.get("window", 20),
            ),
            "zscore_momentum": lambda: FactorGenome.create_zscore_momentum(
                params.get("feature", "close"),
                params.get("momentum_window", 20),
                params.get("zscore_window", 252),
            ),
            "volume_weighted": lambda: FactorGenome.create_volume_weighted(
                params.get("feature", "close"),
                params.get("momentum_window", 20),
                params.get("volume_window", 10),
            ),
        }
        factory = templates.get(template_name)
        return factory() if factory else None

    # ── Analysis ───────────────────────────────────────────

    @staticmethod
    def classify(genome: Genome) -> FactorCategory:
        """Infer the factor category from the genome expression."""
        if not genome.root_gene:
            return FactorCategory.UNKNOWN

        expr = genome.to_expression_string().lower()

        category_keywords = {
            FactorCategory.MOMENTUM: ["momentum", "roc", "rsi", "trend"],
            FactorCategory.VOLATILITY: ["volatility", "vol", "std", "atr"],
            FactorCategory.VOLUME: ["volume", "turnover", "vwap", "adv"],
            FactorCategory.VALUE: ["pe_ratio", "pb_ratio", "ps_ratio", "ev_ebitda"],
            FactorCategory.QUALITY: ["roe", "roa", "gross_margin", "debt_to_equity"],
            FactorCategory.GROWTH: ["growth", "yoy"],
            FactorCategory.LIQUIDITY: ["spread", "illiquidity", "amihud"],
            FactorCategory.CROSS_SECTIONAL: ["cs_rank", "cs_zscore", "group_mean"],
        }

        scores = {}
        for category, keywords in category_keywords.items():
            scores[category] = sum(1 for kw in keywords if kw in expr)

        if not scores:
            return FactorCategory.UNKNOWN

        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else FactorCategory.UNKNOWN

    @staticmethod
    def get_feature_names(genome: Genome) -> Set[str]:
        """Extract all feature names used in the genome."""
        features = set()
        if not genome.root_gene:
            return features
        for gene in genome.root_gene.flatten():
            if gene.type == GeneType.OPERAND:
                features.add(str(gene.value))
        return features

    @staticmethod
    def get_windows(genome: Genome) -> Dict[str, int]:
        """Extract all window/lookback parameters."""
        windows = {}
        if not genome.root_gene:
            return windows
        for gene in genome.root_gene.flatten():
            for key, value in gene.parameters.items():
                if "window" in key.lower() or "lookback" in key.lower():
                    if isinstance(value, (int, float)):
                        windows[key] = int(value)
        return windows
