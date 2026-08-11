"""
Factor Generator — Automated generation of factor candidates.

Generates factor genomes from:
    - Templates (momentum, volatility, value, etc.)
    - Feature pools (price, volume, fundamentals, alternative data)
    - Random combinations of operators and features
    - Evolutionary offspring (from mutation/crossover)
"""

from __future__ import annotations

import random
import uuid
from typing import Any, Dict, List, Optional

from services.alpha_evolution.genome import Genome, GenomeType, ExpressionType
from services.alpha_evolution.gene import (
    Gene,
    GeneFunction,
    GeneOperator,
    GeneType,
)
from services.alpha_evolution.factor_genome import (
    FactorGenome,
    FactorCategory,
    FEATURE_TAXONOMY,
)


class FactorGenerator:
    """
    Generates factor genomes from templates, feature pools, or random combinations.
    """

    def __init__(self, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)

    # ── Template Generation ────────────────────────────────

    def generate_from_template(
        self,
        template_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Genome]:
        """Generate a factor from a named template."""
        return FactorGenome.from_template(template_name, params)

    def generate_template_batch(
        self,
        templates: List[str],
        params_per_template: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Genome]:
        """Generate multiple factors from templates."""
        results = []
        for i, template in enumerate(templates):
            params = params_per_template[i] if params_per_template else {}
            genome = self.generate_from_template(template, params)
            if genome:
                results.append(genome)
        return results

    # ── Random Generation ──────────────────────────────────

    def generate_random(
        self,
        n: int = 10,
        max_depth: int = 3,
        categories: Optional[List[FactorCategory]] = None,
    ) -> List[Genome]:
        """Generate N random factor genomes."""
        results = []
        for _ in range(n):
            genome = self._random_factor(max_depth)
            results.append(genome)
        return results

    def _random_factor(self, max_depth: int = 3) -> Genome:
        """Generate a single random factor genome."""
        genome = Genome(
            genome_type=GenomeType.FACTOR,
            name=f"random_factor_{uuid.uuid4().hex[:6]}",
            creation_method="generated",
        )

        # Build random gene tree
        gene = self._random_gene_tree(max_depth)
        genome.root_gene = gene

        # Random expression type
        genome.expression_type = random.choice([
            ExpressionType.RAW, ExpressionType.RANK, ExpressionType.ZSCORE,
        ])

        return genome

    def _random_gene_tree(self, max_depth: int) -> Gene:
        """Build a random gene tree up to max_depth."""
        if max_depth <= 1 or random.random() < 0.4:
            # Leaf: random operand
            feature = self._random_feature()
            return Gene.operand(feature)

        # Internal node: operator or function
        if random.random() < 0.5:
            # Operator with 2 children
            op = random.choice(list(GeneOperator.__dict__.values()))
            if isinstance(op, str) and len(op) <= 2:
                left = self._random_gene_tree(max_depth - 1)
                right = self._random_gene_tree(max_depth - 1)
                return Gene.operator(op, left, right)

        # Function
        func = self._random_function()
        n_children = 1 if func in (GeneFunction.MOMENTUM, GeneFunction.VOLATILITY,
                                   GeneFunction.ZSCORE, GeneFunction.RANK) else 2
        children = [self._random_gene_tree(max_depth - 1) for _ in range(n_children)]

        params = {}
        if random.random() < 0.6:
            params["window"] = random.choice([5, 10, 20, 30, 60, 120])

        return Gene.function(func, *children, **params)

    def _random_feature(self) -> str:
        """Pick a random feature from the taxonomy."""
        category = random.choice(list(FEATURE_TAXONOMY.keys()))
        return random.choice(FEATURE_TAXONOMY[category])

    def _random_function(self) -> str:
        """Pick a random function."""
        return random.choice([
            GeneFunction.MOMENTUM, GeneFunction.VOLATILITY,
            GeneFunction.MEAN, GeneFunction.STD,
            GeneFunction.ZSCORE, GeneFunction.RANK,
            GeneFunction.ROC, GeneFunction.VOLUME_RATIO,
        ])

    # ── Category-Specific Generation ───────────────────────

    def generate_by_category(
        self,
        category: FactorCategory,
        n: int = 10,
    ) -> List[Genome]:
        """Generate factors of a specific category."""
        results = []
        features = FEATURE_TAXONOMY.get(
            self._category_to_feature_key(category),
            FEATURE_TAXONOMY.get("price", ["close"]),
        )

        for _ in range(n):
            feature = random.choice(features)
            window = random.choice([5, 10, 20, 30, 60, 120])

            genome = Genome(
                genome_type=GenomeType.FACTOR,
                name=f"{category.value}_{uuid.uuid4().hex[:6]}",
                expression_type=ExpressionType.RANK,
                creation_method="generated",
                metadata={"category": category.value},
            )

            if category == FactorCategory.MOMENTUM:
                genome.root_gene = Gene.momentum(feature, window)
            elif category == FactorCategory.VOLATILITY:
                genome.root_gene = Gene.volatility(feature, window)
            else:
                genome.root_gene = Gene.operand(feature)

            results.append(genome)

        return results

    def _category_to_feature_key(self, category: FactorCategory) -> str:
        """Map factor category to feature taxonomy key."""
        mapping = {
            FactorCategory.MOMENTUM: "momentum",
            FactorCategory.VALUE: "value",
            FactorCategory.QUALITY: "quality",
            FactorCategory.VOLATILITY: "volatility",
            FactorCategory.LIQUIDITY: "liquidity",
            FactorCategory.VOLUME: "volume",
            FactorCategory.GROWTH: "growth",
            FactorCategory.SENTIMENT: "sentiment",
        }
        return mapping.get(category, "price")
