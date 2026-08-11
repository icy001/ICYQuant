"""
Factor Composer — Combines multiple factor genomes into composite factor expressions.

Composite methods:
    - Weighted combination: weighted sum of factor values
    - Rank combination: average of cross-sectionally ranked factors
    - Z-score combination: average of normalized factors
    - Nonlinear combination: nonlinear function of factors
    - Conditional combination: regime-based factor selection
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from services.alpha_evolution.genome import Genome, GenomeType, ExpressionType
from services.alpha_evolution.gene import (
    Gene,
    GeneFunction,
    GeneOperator,
)
from services.alpha_evolution.factor_genome import FactorGenome

logger = logging.getLogger(__name__)


class CompositionMethod(Enum):
    WEIGHTED = "weighted"
    EQUAL_WEIGHT = "equal_weight"
    RANK = "rank"
    ZSCORE = "zscore"
    NONLINEAR = "nonlinear"
    CONDITIONAL = "conditional"


class FactorComposer:
    """
    Combines multiple factor genomes into composite expressions.
    """

    def __init__(self):
        pass

    # ── Composition Methods ────────────────────────────────

    def compose(
        self,
        factors: List[Genome],
        method: CompositionMethod = CompositionMethod.EQUAL_WEIGHT,
        weights: Optional[List[float]] = None,
        name: str = "composite_factor",
    ) -> Genome:
        """
        Combine multiple factor genomes into a single composite factor.

        Args:
            factors: List of factor genomes to combine
            method: Composition method
            weights: Optional weights (for weighted method)
            name: Name for the composite factor

        Returns:
            Composite factor genome
        """
        if not factors:
            return FactorGenome.create_empty()

        if len(factors) == 1:
            result = factors[0].clone()
            result.name = name
            return result

        if method == CompositionMethod.EQUAL_WEIGHT:
            return self._equal_weight_compose(factors, name)
        elif method == CompositionMethod.WEIGHTED:
            return self._weighted_compose(factors, weights, name)
        elif method == CompositionMethod.RANK:
            return self._rank_compose(factors, name)
        elif method == CompositionMethod.ZSCORE:
            return self._zscore_compose(factors, name)
        elif method == CompositionMethod.NONLINEAR:
            return self._nonlinear_compose(factors, name)
        else:
            return self._equal_weight_compose(factors, name)

    def _equal_weight_compose(
        self, factors: List[Genome], name: str
    ) -> Genome:
        """Equal-weighted composition."""
        genome = Genome(
            genome_type=GenomeType.FACTOR,
            name=name,
            expression_type=ExpressionType.RANK,
            creation_method="compose",
        )

        valid_factors = [f for f in factors if f.root_gene]
        if not valid_factors:
            return genome

        n = len(valid_factors)
        weight = 1.0 / n

        genome.root_gene = Gene.composite(
            *[(f.root_gene, weight) for f in valid_factors]
        )
        genome.parameters["factor_count"] = n
        genome.parameters["weights"] = [weight] * n
        genome.parameters["composition_method"] = "equal_weight"
        return genome

    def _weighted_compose(
        self,
        factors: List[Genome],
        weights: Optional[List[float]],
        name: str,
    ) -> Genome:
        """Weighted composition."""
        genome = Genome(
            genome_type=GenomeType.FACTOR,
            name=name,
            expression_type=ExpressionType.RANK,
            creation_method="compose",
        )

        valid = [(f, w) for f, w in zip(factors, weights or []) if f.root_gene]
        if not valid:
            return genome

        # Normalize weights
        total = sum(w for _, w in valid)
        normalized = [(f, w / total) for f, w in valid]

        genome.root_gene = Gene.composite(*normalized)
        genome.parameters["factor_count"] = len(valid)
        genome.parameters["weights"] = [w for _, w in normalized]
        genome.parameters["composition_method"] = "weighted"
        return genome

    def _rank_compose(
        self, factors: List[Genome], name: str
    ) -> Genome:
        """Rank-based composition (cross-sectional rank average)."""
        genome = Genome(
            genome_type=GenomeType.FACTOR,
            name=name,
            expression_type=ExpressionType.RANK,
            creation_method="compose",
        )

        valid = [f for f in factors if f.root_gene]
        if not valid:
            return genome

        n = len(valid)
        ranked = [
            Gene.function(GeneFunction.RANK, f.root_gene) for f in valid
        ]

        genome.root_gene = Gene.composite(
            *[(g, 1.0 / n) for g in ranked]
        )
        genome.parameters["factor_count"] = n
        genome.parameters["weights"] = [1.0 / n] * n
        genome.parameters["composition_method"] = "rank"
        return genome

    def _zscore_compose(
        self, factors: List[Genome], name: str
    ) -> Genome:
        """Z-score normalized composition."""
        genome = Genome(
            genome_type=GenomeType.FACTOR,
            name=name,
            expression_type=ExpressionType.ZSCORE,
            creation_method="compose",
        )

        valid = [f for f in factors if f.root_gene]
        if not valid:
            return genome

        n = len(valid)
        zscored = [Gene.zscore(f.root_gene) for f in valid]

        genome.root_gene = Gene.composite(
            *[(g, 1.0 / n) for g in zscored]
        )
        genome.parameters["factor_count"] = n
        genome.parameters["composition_method"] = "zscore"
        return genome

    def _nonlinear_compose(
        self, factors: List[Genome], name: str
    ) -> Genome:
        """Nonlinear composition (multiply two factors)."""
        genome = Genome(
            genome_type=GenomeType.FACTOR,
            name=name,
            expression_type=ExpressionType.RANK,
            creation_method="compose",
        )

        valid = [f for f in factors if f.root_gene]
        if len(valid) < 2:
            return self._equal_weight_compose(factors, name)

        # Multiply the first two, add others
        current = Gene.operator(
            GeneOperator.MUL, valid[0].root_gene, valid[1].root_gene
        )
        for f in valid[2:]:
            current = Gene.operator(GeneOperator.ADD, current, f.root_gene)

        genome.root_gene = current
        genome.parameters["factor_count"] = len(valid)
        genome.parameters["composition_method"] = "nonlinear"
        return genome
