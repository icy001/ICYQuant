"""
Alpha Composer — Composes alpha candidates from factor pool.

Alpha composition methods:
    - Weighted linear: weighted sum of factor values
    - Rank-based: cross-sectional rank combination
    - Z-score: normalized factor aggregation
    - Nonlinear: nonlinear combination (ML, RF, etc.)
    - Regime-based: conditional factor selection
    - Ensemble: multiple alphas combined
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from services.alpha_evolution.genome import Genome, GenomeType, ExpressionType
from services.alpha_evolution.gene import Gene, GeneFunction
from services.alpha_evolution.alpha_genome import (
    AlphaGenome,
    AlphaType,
    CompositionMethod as AlphaCompositionMethod,
)
from services.alpha_evolution.factor_composer import FactorComposer, CompositionMethod

logger = logging.getLogger(__name__)


class AlphaComposer:
    """
    Composes alpha candidates from factor and/or alpha pools.

    Pipeline:
        Factor Pool → Factor Composer → Alpha Candidate
        Alpha Pool → Alpha Composer → Ensemble Alpha
    """

    def __init__(self):
        self._factor_composer = FactorComposer()

    # ── Composition from Factors ───────────────────────────

    def compose_from_factors(
        self,
        factors: List[Genome],
        method: AlphaCompositionMethod = AlphaCompositionMethod.WEIGHTED_SUM,
        weights: Optional[List[float]] = None,
        name: str = "alpha",
        neutralize_sectors: bool = True,
        neutralize_market_cap: bool = True,
    ) -> Genome:
        """
        Compose an alpha from a list of factor genomes.

        Args:
            factors: Factor genomes to combine
            method: Composition method
            weights: Factor weights (for weighted composition)
            name: Alpha name
            neutralize_sectors: Neutralize sector exposure
            neutralize_market_cap: Neutralize market cap exposure

        Returns:
            Alpha genome
        """
        if not factors:
            return AlphaGenome.create_empty()

        if method == AlphaCompositionMethod.WEIGHTED_SUM:
            return AlphaGenome.create_weighted_composite(
                list(zip(factors, weights or [1.0 / len(factors)] * len(factors))),
                name=name,
                neutralize_sectors=neutralize_sectors,
                neutralize_market_cap=neutralize_market_cap,
            )
        elif method == AlphaCompositionMethod.RANK_COMBINATION:
            return AlphaGenome.create_rank_combination(factors, name=name)
        elif method == AlphaCompositionMethod.ZSCORE_COMBINATION:
            return AlphaGenome.create_zscore_combination(factors, name=name)
        else:
            return AlphaGenome.create_weighted_composite(
                list(zip(factors, [1.0 / len(factors)] * len(factors))),
                name=name,
            )

    # ── Ensemble Composition ───────────────────────────────

    def compose_ensemble(
        self,
        alphas: List[Genome],
        weights: Optional[List[float]] = None,
        name: str = "ensemble_alpha",
    ) -> Genome:
        """
        Compose an ensemble from existing alpha genomes.

        An ensemble alpha combines multiple alpha signals through weighted averaging.
        """
        if not alphas:
            return AlphaGenome.create_empty()

        n = len(alphas)
        w = weights or [1.0 / n] * n

        genome = Genome(
            genome_type=GenomeType.ALPHA,
            name=name,
            expression_type=ExpressionType.RANK,
            creation_method="compose",
        )

        valid = [(a, w[i]) for i, a in enumerate(alphas) if a.root_gene]
        if not valid:
            return genome

        w_sum = sum(v[1] for v in valid)
        normalized = [(a.root_gene, wt / w_sum) for a, wt in valid]

        genome.root_gene = Gene.composite(*normalized)
        genome.parameters["alpha_count"] = len(valid)
        genome.parameters["weights"] = [wt for _, wt in normalized]
        genome.parameters["composition_method"] = "ensemble"
        genome.metadata["alpha_type"] = AlphaType.ENSEMBLE.value

        return genome

    # ── Smart Composition ──────────────────────────────────

    def compose_optimal(
        self,
        factors: List[Genome],
        fitness_scores: Dict[str, float],
        top_n: int = 5,
        name: str = "optimal_alpha",
    ) -> Genome:
        """
        Compose an alpha using only the top-N performing factors by fitness.

        Args:
            factors: All factor genomes
            fitness_scores: Fitness score per factor ID
            top_n: Number of top factors to use
            name: Alpha name

        Returns:
            Alpha genome using only the best factors
        """
        if not factors or not fitness_scores:
            return AlphaGenome.create_empty()

        # Sort factors by fitness
        scored_factors = sorted(
            factors,
            key=lambda f: fitness_scores.get(f.genome_id, 0),
            reverse=True,
        )
        top_factors = scored_factors[:top_n]

        if not top_factors:
            return AlphaGenome.create_empty()

        # Use fitness-proportional weights
        top_fitnesses = [fitness_scores.get(f.genome_id, 0) for f in top_factors]
        total_fitness = sum(top_fitnesses) or 1.0
        weights = [f / total_fitness for f in top_fitnesses]

        return self.compose_from_factors(
            top_factors,
            method=AlphaCompositionMethod.WEIGHTED_SUM,
            weights=weights,
            name=name,
        )
