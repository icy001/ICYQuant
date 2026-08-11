"""
Alpha Genome — Specialized genome for alpha (multi-factor composite) expressions.

An Alpha Genome encodes a combination of factor genomes into a unified
alpha expression. It supports:
    - Weighted combination of factor genomes
    - Conditional (regime-based) factor switching
    - Nonlinear composition
    - Sector/industry neutralization
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

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


class AlphaType(Enum):
    """Types of alpha strategies."""

    CROSS_SECTIONAL = "cross_sectional"
    TIME_SERIES = "time_series"
    EVENT_DRIVEN = "event_driven"
    REGIME_SWITCHING = "regime_switching"
    ENSEMBLE = "ensemble"
    COMPOSITE = "composite"


class CompositionMethod(Enum):
    """Methods for combining factors into an alpha."""

    WEIGHTED_SUM = "weighted_sum"
    RANK_COMBINATION = "rank_combination"
    ZSCORE_COMBINATION = "zscore_combination"
    NONLINEAR = "nonlinear"
    CONDITIONAL = "conditional"
    MACHINE_LEARNING = "machine_learning"


class AlphaGenome:
    """
    Factory and utilities for alpha-specific genomes.

    Alpha = weighted or nonlinear combination of Factor Genomes.

    Lifecycle:
        Factor Pool → Alpha Composer → Alpha Genome → Validate → Evolve
    """

    # ── Factory Methods ────────────────────────────────────

    @staticmethod
    def create_empty() -> Genome:
        """Create an empty alpha genome."""
        return Genome(
            genome_type=GenomeType.ALPHA,
            name="empty_alpha",
            creation_method="seed",
        )

    @staticmethod
    def create_weighted_composite(
        factors: List[Tuple[Genome, float]],
        name: str = "alpha_composite",
        neutralize_sectors: bool = True,
        neutralize_market_cap: bool = True,
    ) -> Genome:
        """
        Create an alpha genome from a weighted combination of factor genomes.

        Args:
            factors: List of (factor_genome, weight) tuples
            name: Alpha name
            neutralize_sectors: Whether to neutralize sector exposure
            neutralize_market_cap: Whether to neutralize market cap
        """
        genome = Genome(
            genome_type=GenomeType.ALPHA,
            name=name,
            expression_type=ExpressionType.RANK,
            creation_method="seed",
        )

        # Build composite gene tree
        factor_genes = []
        weights = []
        for factor_genome, weight in factors:
            if factor_genome.root_gene:
                factor_genes.append(factor_genome.root_gene)
                weights.append(weight)

        if factor_genes:
            if len(factor_genes) == 1:
                genome.root_gene = factor_genes[0]
            else:
                genome.root_gene = Gene.composite(
                    *[(g, w) for g, w in zip(factor_genes, weights)]
                )

        # Neutralization config
        if neutralize_sectors:
            genome.neutralization = genome.neutralization or {}
            genome.neutralization["sectors"] = True
        if neutralize_market_cap:
            genome.neutralization = genome.neutralization or {}
            genome.neutralization["market_cap"] = True

        genome.parameters["composition_method"] = CompositionMethod.WEIGHTED_SUM.value
        genome.parameters["factor_count"] = len(factors)
        genome.parameters["weights"] = weights

        return genome

    @staticmethod
    def create_rank_combination(
        factors: List[Genome],
        name: str = "alpha_rank_combo",
    ) -> Genome:
        """Create an alpha genome by averaging rank-transformed factors."""
        genome = Genome(
            genome_type=GenomeType.ALPHA,
            name=name,
            expression_type=ExpressionType.RANK,
            creation_method="seed",
        )

        ranked_factors = [
            Gene.function(GeneFunction.RANK, f.root_gene)
            for f in factors
            if f.root_gene
        ]
        if ranked_factors:
            equal_weight = 1.0 / len(ranked_factors)
            genome.root_gene = Gene.composite(
                *[(g, equal_weight) for g in ranked_factors]
            )

        genome.parameters["composition_method"] = CompositionMethod.RANK_COMBINATION.value
        genome.parameters["factor_count"] = len(factors)
        return genome

    @staticmethod
    def create_conditional_alpha(
        regime_detector: Genome,
        bullish_alpha: Genome,
        bearish_alpha: Genome,
        neutral_alpha: Optional[Genome] = None,
        name: str = "alpha_conditional",
    ) -> Genome:
        """Create a regime-switching conditional alpha genome."""
        genome = Genome(
            genome_type=GenomeType.ALPHA,
            name=name,
            creation_method="seed",
        )

        if neutral_alpha and neutral_alpha.root_gene:
            # 3-way regime switch
            is_bull = Gene.operator(
                GeneOperator.GT,
                regime_detector.root_gene or Gene.operand(0),
                Gene.operand(0.5),
            )
            genome.root_gene = Gene.conditional(
                is_bull,
                bullish_alpha.root_gene or Gene.operand(0),
                bearish_alpha.root_gene or Gene.operand(0),
            )
        else:
            # Binary regime switch
            is_bull = Gene.operator(
                GeneOperator.GT,
                regime_detector.root_gene or Gene.operand(0),
                Gene.operand(0),
            )
            genome.root_gene = Gene.conditional(
                is_bull,
                bullish_alpha.root_gene or Gene.operand(0),
                bearish_alpha.root_gene or Gene.operand(0),
            )

        genome.parameters["composition_method"] = CompositionMethod.CONDITIONAL.value
        return genome

    @staticmethod
    def create_zscore_combination(
        factors: List[Genome],
        name: str = "alpha_zscore_combo",
    ) -> Genome:
        """Create an alpha genome by combining z-score normalized factors."""
        genome = Genome(
            genome_type=GenomeType.ALPHA,
            name=name,
            expression_type=ExpressionType.ZSCORE,
            creation_method="seed",
        )

        zscored = [
            Gene.zscore(f.root_gene) for f in factors if f.root_gene
        ]
        if zscored:
            equal_weight = 1.0 / len(zscored)
            genome.root_gene = Gene.composite(
                *[(g, equal_weight) for g in zscored]
            )

        genome.parameters["composition_method"] = CompositionMethod.ZSCORE_COMBINATION.value
        genome.parameters["factor_count"] = len(factors)
        return genome

    # ── Analysis ───────────────────────────────────────────

    @staticmethod
    def classify_alpha(genome: Genome) -> AlphaType:
        """Infer the alpha type from the genome."""
        if not genome.root_gene:
            return AlphaType.COMPOSITE

        comp_method = genome.parameters.get(
            "composition_method", ""
        )
        if comp_method == CompositionMethod.CONDITIONAL.value:
            return AlphaType.REGIME_SWITCHING

        if comp_method == CompositionMethod.WEIGHTED_SUM.value:
            n_factors = genome.parameters.get("factor_count", 0)
            if n_factors > 10:
                return AlphaType.ENSEMBLE
            return AlphaType.COMPOSITE

        if comp_method == CompositionMethod.RANK_COMBINATION.value:
            return AlphaType.CROSS_SECTIONAL

        expr = genome.to_expression_string().lower()
        if "event" in expr or "earnings" in expr:
            return AlphaType.EVENT_DRIVEN

        return AlphaType.COMPOSITE

    @staticmethod
    def get_factor_count(genome: Genome) -> int:
        """Count the number of distinct factors in the alpha genome."""
        return genome.parameters.get("factor_count", 0)

    @staticmethod
    def has_neutralization(genome: Genome) -> bool:
        """Check if the alpha has neutralization configured."""
        return bool(genome.neutralization)

    @staticmethod
    def get_composition_method(genome: Genome) -> Optional[CompositionMethod]:
        """Get the composition method used."""
        method = genome.parameters.get("composition_method")
        if method:
            try:
                return CompositionMethod(method)
            except ValueError:
                pass
        return None

    # ── Templates ──────────────────────────────────────────

    @staticmethod
    def from_template(
        template_name: str,
        factor_genomes: List[Genome],
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Genome]:
        """Create an alpha genome from a named template."""
        params = params or {}
        weights = params.get("weights")

        if template_name == "equal_weight":
            w = [1.0 / len(factor_genomes)] * len(factor_genomes)
            return AlphaGenome.create_weighted_composite(
                list(zip(factor_genomes, w))
            )
        elif template_name == "weighted":
            if not weights:
                weights = [1.0 / len(factor_genomes)] * len(factor_genomes)
            return AlphaGenome.create_weighted_composite(
                list(zip(factor_genomes, weights))
            )
        elif template_name == "rank_combo":
            return AlphaGenome.create_rank_combination(factor_genomes)
        elif template_name == "zscore_combo":
            return AlphaGenome.create_zscore_combination(factor_genomes)

        return None
