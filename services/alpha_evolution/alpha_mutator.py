"""
Alpha Mutator — Applies mutation operations to alpha (multi-factor) genomes.

Alpha-specific mutations:
    - Weight perturbation (adjust factor weights)
    - Factor substitution (swap one factor for another)
    - Factor addition/removal (add or drop a factor from composition)
    - Composition method change
    - Neutralization toggle
    - Regime threshold adjustment (for conditional alphas)
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from services.alpha_evolution.genome import Genome, GenomeType
from services.alpha_evolution.gene import Gene, GeneType
from services.alpha_evolution.alpha_genome import CompositionMethod


class AlphaMutator:
    """
    Mutation operations for alpha (multi-factor composition) genomes.
    """

    def __init__(self, mutation_rate: float = 0.30, seed: Optional[int] = None):
        self._mutation_rate = mutation_rate
        if seed is not None:
            random.seed(seed)

    # ── Mutation Operations ────────────────────────────────

    def mutate(self, genome: Genome) -> Genome:
        """Apply a random alpha-specific mutation."""
        if not genome.root_gene:
            return genome.clone()

        mutated = genome.copy_for_mutation()

        mutation_type = random.choice([
            "weight", "factor_substitution", "factor_count",
            "neutralization", "composition_method",
        ])

        if mutation_type == "weight":
            self._mutate_weights(mutated)
        elif mutation_type == "factor_substitution":
            pass  # Requires factor pool reference
        elif mutation_type == "factor_count":
            self._mutate_factor_count(mutated)
        elif mutation_type == "neutralization":
            self._mutate_neutralization(mutated)
        elif mutation_type == "composition_method":
            self._mutate_composition_method(mutated)

        return mutated

    def _mutate_weights(self, genome: Genome) -> None:
        """Perturb factor weights in the composition."""
        weights = genome.parameters.get("weights", [])
        if not weights:
            return

        # Perturb one random weight and re-normalize
        idx = random.randrange(len(weights))
        perturbation = random.uniform(-0.20, 0.20)
        weights[idx] = max(0.01, weights[idx] + perturbation)

        # Re-normalize
        total = sum(weights)
        weights = [w / total for w in weights]

        genome.parameters["weights"] = weights
        genome.version += 1

    def _mutate_factor_count(self, genome: Genome) -> None:
        """Add or remove a factor from the composition."""
        n_factors = genome.parameters.get("factor_count", 0)

        if random.random() < 0.5 and n_factors > 2:
            # Remove one
            n_factors -= 1
        else:
            # Add one
            n_factors += 1

        genome.parameters["factor_count"] = n_factors
        # Recompute equal weights
        genome.parameters["weights"] = [1.0 / n_factors] * n_factors
        genome.version += 1

    def _mutate_neutralization(self, genome: Genome) -> None:
        """Toggle or change neutralization settings."""
        if genome.neutralization:
            # Toggle specific neutralizations
            if "sectors" in genome.neutralization:
                del genome.neutralization["sectors"]
            elif "market_cap" in genome.neutralization:
                del genome.neutralization["market_cap"]
            else:
                genome.neutralization["sectors"] = True
        else:
            genome.neutralization = {"sectors": True}
        genome.version += 1

    def _mutate_composition_method(self, genome: Genome) -> None:
        """Change the composition method."""
        methods = [m.value for m in CompositionMethod]
        current = genome.parameters.get("composition_method", "")
        new_method = random.choice([m for m in methods if m != current])
        genome.parameters["composition_method"] = new_method
        genome.version += 1
