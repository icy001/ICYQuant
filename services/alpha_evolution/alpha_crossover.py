"""
Alpha Crossover — Crossover operations for alpha (multi-factor) genomes.

Alpha crossover combines factor compositions from two parent alphas:
    - Factor mix: blend factor sets from both parents
    - Weight crossover: cross weight vectors
    - Neutralization mix: combine neutralization settings
    - Regime rule mix: combine conditional rules
"""

from __future__ import annotations

import random
from typing import List, Optional

from services.alpha_evolution.genome import Genome


class AlphaCrossover:
    """
    Crossover operations for alpha genomes.
    """

    def __init__(self, crossover_rate: float = 0.40, seed: Optional[int] = None):
        self._crossover_rate = crossover_rate
        if seed is not None:
            random.seed(seed)

    def crossover(
        self, parent_a: Genome, parent_b: Genome
    ) -> Genome:
        """Perform crossover between two parent alpha genomes."""
        if not parent_a.root_gene or not parent_b.root_gene:
            return parent_a.clone()

        crossover_type = random.choice([
            "factor_mix", "weight_crossover", "neutralization_mix",
        ])

        if crossover_type == "factor_mix":
            return self._factor_mix(parent_a, parent_b)
        elif crossover_type == "weight_crossover":
            return self._weight_crossover(parent_a, parent_b)
        elif crossover_type == "neutralization_mix":
            return self._neutralization_mix(parent_a, parent_b)

        return parent_a.clone()

    def _factor_mix(
        self, parent_a: Genome, parent_b: Genome
    ) -> Genome:
        """Mix factor sets from both parents."""
        child = parent_a.copy_for_crossover(parent_b)

        count_a = parent_a.parameters.get("factor_count", 0)
        count_b = parent_b.parameters.get("factor_count", 0)
        new_count = max(1, (count_a + count_b) // 2)

        child.parameters["factor_count"] = new_count
        child.parameters["weights"] = [1.0 / new_count] * new_count

        # Mix neutralization
        if parent_a.neutralization or parent_b.neutralization:
            child.neutralization = {}
            if parent_a.neutralization:
                child.neutralization.update(parent_a.neutralization)
            if parent_b.neutralization:
                child.neutralization.update(parent_b.neutralization)

        child.version += 1
        return child

    def _weight_crossover(
        self, parent_a: Genome, parent_b: Genome
    ) -> Genome:
        """Cross weight vectors between two alphas."""
        child = parent_a.copy_for_crossover(parent_b)

        weights_a = parent_a.parameters.get("weights", [])
        weights_b = parent_b.parameters.get("weights", [])

        if not weights_a or not weights_b:
            return child

        # Interleave weights
        min_len = min(len(weights_a), len(weights_b))
        new_weights = []
        for i in range(min_len):
            new_weights.append(
                weights_a[i] if random.random() < 0.5 else weights_b[i]
            )

        # Normalize
        total = sum(new_weights)
        child.parameters["weights"] = [w / total for w in new_weights] if total > 0 else new_weights
        child.parameters["factor_count"] = min_len
        child.version += 1
        return child

    def _neutralization_mix(
        self, parent_a: Genome, parent_b: Genome
    ) -> Genome:
        """Combine neutralization settings from both parents."""
        child = parent_a.copy_for_crossover(parent_b)

        child.neutralization = {}
        neut_a = parent_a.neutralization or {}
        neut_b = parent_b.neutralization or {}

        for key in set(list(neut_a.keys()) + list(neut_b.keys())):
            if random.random() < 0.5 and key in neut_a:
                child.neutralization[key] = neut_a[key]
            elif key in neut_b:
                child.neutralization[key] = neut_b[key]

        child.version += 1
        return child
