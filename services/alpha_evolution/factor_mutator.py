"""
Factor Mutator — Applies mutation operations specifically to factor genomes.

Supported mutations:
    - Parameter mutation (change window, threshold, etc.)
    - Operator mutation (swap + with *, etc.)
    - Feature mutation (replace input feature)
    - Window mutation (change lookback period)
    - Transformation mutation (add/remove zscore, rank, etc.)
    - Structure mutation (add/remove sub-expressions)
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from services.alpha_evolution.genome import Genome, ExpressionType
from services.alpha_evolution.gene import (
    Gene,
    GeneFunction,
    GeneOperator,
    GeneType,
)
from services.alpha_evolution.factor_genome import FEATURE_TAXONOMY


# Available features for mutation
_ALL_FEATURES = []
for category, features in FEATURE_TAXONOMY.items():
    _ALL_FEATURES.extend(features)

_OPERATORS = [GeneOperator.ADD, GeneOperator.SUB, GeneOperator.MUL, GeneOperator.DIV]
_TRANSFORMATIONS = [
    GeneFunction.ZSCORE, GeneFunction.RANK, GeneFunction.WINSORIZE,
    GeneFunction.NEUTRALIZE,
]
_FUNCTIONS = [
    GeneFunction.MOMENTUM, GeneFunction.VOLATILITY, GeneFunction.ROC,
    GeneFunction.EMA, GeneFunction.MEAN, GeneFunction.STD,
    GeneFunction.VOLUME_RATIO, GeneFunction.VWAP,
]
_WINDOWS = [5, 10, 20, 30, 60, 90, 120, 252]


class FactorMutator:
    """
    Mutation operations for factor genomes.

    Each mutation method returns a new mutated Genome.
    """

    def __init__(self, mutation_rate: float = 0.30, seed: Optional[int] = None):
        self._mutation_rate = mutation_rate
        if seed is not None:
            random.seed(seed)

    # ── Mutation Operations ────────────────────────────────

    def mutate(self, genome: Genome) -> Genome:
        """Apply a random mutation to the genome."""
        if not genome.root_gene:
            return genome.clone()

        mutated = genome.copy_for_mutation()

        mutation_type = random.choice([
            "parameter", "operator", "feature", "window",
            "transformation", "structure",
        ])

        if mutation_type == "parameter":
            self._mutate_parameter(mutated)
        elif mutation_type == "operator":
            self._mutate_operator(mutated)
        elif mutation_type == "feature":
            self._mutate_feature(mutated)
        elif mutation_type == "window":
            self._mutate_window(mutated)
        elif mutation_type == "transformation":
            self._mutate_transformation(mutated)
        elif mutation_type == "structure":
            self._mutate_structure(mutated)

        return mutated

    def _mutate_parameter(self, genome: Genome) -> None:
        """Mutate a random parameter in the genome."""
        all_params = dict(genome.parameters)
        operator_genes = genome.root_gene.get_operators()
        func_genes = genome.root_gene.get_functions()

        # Collect all mutable parameters
        mutable: List[tuple[str, Any]] = []
        for key, value in all_params.items():
            if isinstance(value, (int, float)):
                mutable.append(("global", key, value))

        for gene in func_genes:
            for key, value in gene.parameters.items():
                if isinstance(value, (int, float)):
                    mutable.append(("gene", key, value))

        if not mutable:
            return

        scope, key, old_value = random.choice(mutable)

        if isinstance(old_value, int):
            new_value = old_value + random.choice([-5, -2, -1, 1, 2, 5])
            new_value = max(1, new_value)
        else:
            new_value = old_value * random.uniform(0.5, 1.5)
            new_value = round(new_value, 2)

        if scope == "global":
            genome.mutate_parameter(key, new_value)
        else:
            # Mutate in a random function gene
            target = random.choice(func_genes)
            target.parameters[key] = new_value
            genome.version += 1

    def _mutate_operator(self, genome: Genome) -> None:
        """Swap an operator (+, -, *, /) in the gene tree."""
        operators = genome.root_gene.get_operators()
        if not operators:
            return

        target = random.choice(operators)
        old_op = target.value
        new_op = random.choice([op for op in _OPERATORS if op != old_op])
        target.value = new_op
        genome.version += 1

    def _mutate_feature(self, genome: Genome) -> None:
        """Replace one feature operand with another."""
        operands = genome.root_gene.get_leaf_operands()
        if not operands:
            return

        target = random.choice(operands)
        old_feature = str(target.value)
        new_feature = random.choice(
            [f for f in _ALL_FEATURES if f != old_feature]
        )
        target.value = new_feature
        genome.version += 1

    def _mutate_window(self, genome: Genome) -> None:
        """Change a lookback window parameter."""
        func_genes = genome.root_gene.get_functions()
        window_params: List[tuple[Gene, str, int]] = []

        for gene in func_genes:
            for key, value in gene.parameters.items():
                if "window" in key.lower() and isinstance(value, (int, float)):
                    window_params.append((gene, key, int(value)))

        if not window_params:
            return

        gene, key, old_window = random.choice(window_params)
        new_window = random.choice([w for w in _WINDOWS if w != old_window])
        gene.parameters[key] = new_window
        genome.version += 1

    def _mutate_transformation(self, genome: Genome) -> None:
        """Add, remove, or change a transformation (zscore, rank, etc.)."""
        # Wrap root_gene in a new transformation
        new_transform = random.choice(_TRANSFORMATIONS)
        genome.root_gene = Gene.function(new_transform, genome.root_gene)
        genome.version += 1

    def _mutate_structure(self, genome: Genome) -> None:
        """Structural mutation: add or remove a sub-expression."""
        if random.random() < 0.5 and genome.root_gene.depth() > 1:
            # Simplify: remove a random child
            func_genes = genome.root_gene.get_functions()
            candidates = [g for g in func_genes if g.children]
            if candidates:
                target = random.choice(candidates)
                if target.children:
                    target.remove_child(random.randrange(len(target.children)))
                    genome.version += 1
        else:
            # Add: multiply by a new feature
            new_feature = random.choice(_ALL_FEATURES)
            genome.root_gene = Gene.operator(
                GeneOperator.MUL,
                genome.root_gene,
                Gene.operand(new_feature),
            )
            genome.version += 1
