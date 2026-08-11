"""
Factor Crossover — Crossover operations for factor genomes.

Crossover combines two parent factor genomes to produce offspring with
mixed characteristics. Supported crossover types:
    - Single-point: swap subtrees at a random point
    - Uniform: randomly select genes from either parent
    - Arithmetic: blend numerical parameters
"""

from __future__ import annotations

import random
from typing import Optional

from services.alpha_evolution.genome import Genome


class FactorCrossover:
    """
    Crossover operations for factor genomes.

    Produces one or more offspring genomes from two parent factor genomes.
    """

    def __init__(self, crossover_rate: float = 0.40, seed: Optional[int] = None):
        self._crossover_rate = crossover_rate
        if seed is not None:
            random.seed(seed)

    def crossover(
        self, parent_a: Genome, parent_b: Genome
    ) -> Genome:
        """Perform crossover between two parent factor genomes."""
        if not parent_a.root_gene or not parent_b.root_gene:
            # Fall back to cloning the better parent
            return parent_a.clone()

        # Choose crossover type
        crossover_type = random.choice([
            "single_point", "uniform", "arithmetic",
        ])

        if crossover_type == "single_point":
            return self._single_point_crossover(parent_a, parent_b)
        elif crossover_type == "uniform":
            return self._uniform_crossover(parent_a, parent_b)
        elif crossover_type == "arithmetic":
            return self._arithmetic_crossover(parent_a, parent_b)

        return parent_a.clone()

    def _single_point_crossover(
        self, parent_a: Genome, parent_b: Genome
    ) -> Genome:
        """Single-point: cut gene trees at a point and swap subtrees."""
        child = parent_a.copy_for_crossover(parent_b)

        genes_a = parent_a.root_gene.flatten()
        genes_b = parent_b.root_gene.flatten()

        if not genes_a or not genes_b:
            return child

        # Pick crossover point
        point_a = random.randrange(len(genes_a))
        point_b = random.randrange(len(genes_b))

        # Swap genes at crossover point
        node_a = genes_a[point_a]
        node_b = genes_b[point_b]

        # Swap values
        node_a.value, node_b.value = node_b.value, node_a.value
        # Swap parameters
        node_a.parameters, node_b.parameters = node_b.parameters, node_a.parameters

        child.root_gene = parent_a.root_gene
        child.version += 1
        return child

    def _uniform_crossover(
        self, parent_a: Genome, parent_b: Genome
    ) -> Genome:
        """Uniform: randomly select parameters from either parent."""
        child = parent_a.copy_for_crossover(parent_b)

        # Merge parameters with 50/50 selection
        for key in set(list(parent_a.parameters.keys()) + list(parent_b.parameters.keys())):
            if random.random() < 0.5:
                if key in parent_a.parameters:
                    child.parameters[key] = parent_a.parameters[key]
            else:
                if key in parent_b.parameters:
                    child.parameters[key] = parent_b.parameters[key]

        child.version += 1
        return child

    def _arithmetic_crossover(
        self, parent_a: Genome, parent_b: Genome
    ) -> Genome:
        """Arithmetic: blend numerical parameters."""
        child = parent_a.copy_for_crossover(parent_b)

        alpha = random.random()  # blend factor

        for key in set(list(parent_a.parameters.keys()) + list(parent_b.parameters.keys())):
            val_a = parent_a.parameters.get(key)
            val_b = parent_b.parameters.get(key)

            if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                child.parameters[key] = alpha * val_a + (1 - alpha) * val_b
            elif isinstance(val_a, (int, float)):
                child.parameters[key] = val_a
            elif isinstance(val_b, (int, float)):
                child.parameters[key] = val_b

        child.version += 1
        return child
