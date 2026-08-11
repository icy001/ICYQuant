"""
Alpha Generator — Automated generation of alpha candidates from factor pools.

Generates alpha genomes by:
    - Combining top-performing factors
    - Random factor sampling and composition
    - Template-based alpha construction
    - Pareto-optimal factor selection
    - Regime-specific alpha generation
"""

from __future__ import annotations

import random
import uuid
from typing import Any, Dict, List, Optional

from services.alpha_evolution.genome import Genome
from services.alpha_evolution.alpha_genome import (
    AlphaGenome,
    AlphaType,
    CompositionMethod,
)
from services.alpha_evolution.alpha_composer import AlphaComposer


class AlphaGenerator:
    """
    Generates alpha candidates from factor pools.

    Generation strategies:
        - Top-N: use N best factors
        - Random: randomly sample factors
        - Exhaustive: try all nCr combinations (controlled by budget)
        - Template: use predefined alpha templates
    """

    def __init__(self, seed: Optional[int] = None):
        self._composer = AlphaComposer()
        if seed is not None:
            random.seed(seed)

    # ── Top-N Generation ───────────────────────────────────

    def generate_top_n(
        self,
        factors: List[Genome],
        fitness_scores: Dict[str, float],
        top_n: int = 5,
        n_alphas: int = 3,
    ) -> List[Genome]:
        """
        Generate alphas using top-N factors by fitness.

        Uses different composition methods across generated alphas.
        """
        if len(factors) < 2:
            return []

        # Sort by fitness
        scored = sorted(
            factors, key=lambda f: fitness_scores.get(f.genome_id, 0), reverse=True
        )
        best = scored[:max(top_n, 2)]

        alphas = []
        methods = [
            CompositionMethod.WEIGHTED_SUM,
            CompositionMethod.RANK_COMBINATION,
            CompositionMethod.ZSCORE_COMBINATION,
        ]

        for i in range(min(n_alphas, len(methods))):
            method = methods[i]
            alpha = self._composer.compose_from_factors(
                best,
                method=method,
                name=f"alpha_top{top_n}_{method.value}",
            )
            alphas.append(alpha)

        return alphas

    # ── Random Generation ──────────────────────────────────

    def generate_random(
        self,
        factors: List[Genome],
        n_alphas: int = 10,
        min_factors: int = 2,
        max_factors: int = 5,
    ) -> List[Genome]:
        """
        Generate alphas from random factor subsets.

        Args:
            factors: Factor pool
            n_alphas: Number of alphas to generate
            min_factors: Minimum factors per alpha
            max_factors: Maximum factors per alpha
        """
        if len(factors) < min_factors:
            return []

        alphas = []
        for _ in range(n_alphas):
            n_pick = random.randint(min_factors, min(max_factors, len(factors)))
            subset = random.sample(factors, n_pick)

            method = random.choice([
                CompositionMethod.WEIGHTED_SUM,
                CompositionMethod.RANK_COMBINATION,
            ])

            weights = None
            if method == CompositionMethod.WEIGHTED_SUM:
                raw = [random.random() for _ in range(n_pick)]
                total = sum(raw)
                weights = [w / total for w in raw]

            alpha = self._composer.compose_from_factors(
                subset,
                method=method,
                weights=weights,
                name=f"alpha_random_{uuid.uuid4().hex[:6]}",
            )
            alphas.append(alpha)

        return alphas

    # ── Fitness-Proportional Generation ────────────────────

    def generate_fitness_weighted(
        self,
        factors: List[Genome],
        fitness_scores: Dict[str, float],
        n_alphas: int = 10,
        min_factors: int = 2,
        max_factors: int = 5,
    ) -> List[Genome]:
        """
        Generate alphas with fitness-proportional factor selection.

        Higher-fitness factors are more likely to be selected.
        """
        if len(factors) < min_factors:
            return []

        # Build fitness-weighted sampling pool
        fitnesses = [fitness_scores.get(f.genome_id, 0.001) for f in factors]
        total_fitness = sum(fitnesses) or 1.0

        alphas = []
        for _ in range(n_alphas):
            n_pick = random.randint(min_factors, min(max_factors, len(factors)))
            # Weighted sampling without replacement
            selected = self._weighted_sample(factors, fitnesses, n_pick)

            alpha = self._composer.compose_from_factors(
                selected,
                method=CompositionMethod.WEIGHTED_SUM,
                weights=[fitness_scores.get(f.genome_id, 0.001) for f in selected],
                name=f"alpha_fit_{uuid.uuid4().hex[:6]}",
            )
            alphas.append(alpha)

        return alphas

    def _weighted_sample(
        self,
        items: List[Genome],
        weights: List[float],
        k: int,
    ) -> List[Genome]:
        """Weighted sampling without replacement."""
        available = list(range(len(items)))
        selected = []
        remaining_weights = list(weights)

        for _ in range(min(k, len(available))):
            total = sum(remaining_weights) or 1.0
            probs = [w / total for w in remaining_weights]
            # Roulette wheel selection
            r = random.random()
            cumulative = 0.0
            chosen_idx = 0
            for i, p in enumerate(probs):
                cumulative += p
                if r <= cumulative:
                    chosen_idx = i
                    break

            selected.append(items[available[chosen_idx]])
            del available[chosen_idx]
            del remaining_weights[chosen_idx]

        return selected

    # ── Template-Based Generation ──────────────────────────

    def generate_from_template(
        self,
        factors: List[Genome],
        template_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Genome]:
        """Generate an alpha using a named template."""
        return AlphaGenome.from_template(template_name, factors, params)

    # ── Batch Generation ───────────────────────────────────

    def generate_all(
        self,
        factors: List[Genome],
        fitness_scores: Optional[Dict[str, float]] = None,
        n_total: int = 20,
    ) -> List[Genome]:
        """
        Generate a diverse batch of alphas using multiple strategies.

        Mix:
            - Top-N: 30% of budget
            - Random: 30% of budget
            - Fitness-weighted: 40% of budget
        """
        if len(factors) < 2:
            return []

        n_top = max(1, int(n_total * 0.30))
        n_random = max(1, int(n_total * 0.30))
        n_fitness = n_total - n_top - n_random

        alphas = []

        if fitness_scores:
            alphas.extend(self.generate_top_n(factors, fitness_scores, top_n=5, n_alphas=n_top))
        else:
            alphas.extend(self.generate_random(factors, n_alphas=n_top))

        alphas.extend(self.generate_random(factors, n_alphas=n_random))

        if fitness_scores:
            alphas.extend(self.generate_fitness_weighted(
                factors, fitness_scores, n_alphas=n_fitness
            ))
        else:
            alphas.extend(self.generate_random(factors, n_alphas=n_fitness))

        return alphas
