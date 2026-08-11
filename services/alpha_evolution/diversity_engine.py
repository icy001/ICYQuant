"""
Diversity Engine — Maintains population diversity across evolution.

Prevents the population from converging to a single type of factor/alpha.
Measures and enforces diversity across dimensions:
    - Factor category diversity
    - Feature usage diversity
    - Expression structure diversity
    - Return profile diversity
    - Regime response diversity
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from services.alpha_evolution.genome import Genome
from services.alpha_evolution.factor_genome import FactorCategory, FactorGenome

logger = logging.getLogger(__name__)


class DiversityDimension(Enum):
    CATEGORY = "category"
    FEATURE = "feature"
    EXPRESSION = "expression"
    RETURN_PROFILE = "return_profile"
    REGIME = "regime"


class DiversityEngine:
    """
    Tracks and enforces population diversity.

    Diversity is essential to prevent:
        - Convergence to homogeneous factor types
        - Loss of exploration capability
        - Alpha zoo full of redundant strategies
    """

    def __init__(
        self,
        diversity_target: float = 0.40,
        min_category_diversity: float = 0.20,
        min_feature_diversity: float = 0.30,
    ):
        self._diversity_target = diversity_target
        self._min_category_diversity = min_category_diversity
        self._min_feature_diversity = min_feature_diversity
        self._diversity_history: List[Dict[str, float]] = []

    # ── Diversity Measurement ──────────────────────────────

    def compute_diversity(
        self, genomes: List[Genome]
    ) -> Dict[str, float]:
        """Compute multi-dimensional diversity scores."""
        if not genomes:
            return {dim.value: 0.0 for dim in DiversityDimension}

        return {
            DiversityDimension.CATEGORY.value: self._category_diversity(genomes),
            DiversityDimension.FEATURE.value: self._feature_diversity(genomes),
            DiversityDimension.EXPRESSION.value: self._expression_diversity(genomes),
            DiversityDimension.RETURN_PROFILE.value: self._return_profile_diversity(genomes),
        }

    def overall_diversity(self, genomes: List[Genome]) -> float:
        """Compute overall population diversity (0-1)."""
        scores = self.compute_diversity(genomes)
        weights = {
            DiversityDimension.CATEGORY.value: 0.25,
            DiversityDimension.FEATURE.value: 0.25,
            DiversityDimension.EXPRESSION.value: 0.25,
            DiversityDimension.RETURN_PROFILE.value: 0.25,
        }
        return sum(scores[k] * weights.get(k, 0) for k in scores)

    # ── Individual Dimensions ──────────────────────────────

    def _category_diversity(self, genomes: List[Genome]) -> float:
        """Diversity of factor categories in the population."""
        categories: Dict[str, int] = {}
        for g in genomes:
            cat = FactorGenome.classify(g)
            categories[cat.value] = categories.get(cat.value, 0) + 1

        if not categories:
            return 0.0

        n = len(genomes)
        # Shannon entropy based diversity
        import math
        entropy = 0.0
        for count in categories.values():
            p = count / n
            entropy -= p * math.log(p) if p > 0 else 0

        max_entropy = math.log(len(categories)) if categories else 1
        return entropy / max_entropy if max_entropy > 0 else 0

    def _feature_diversity(self, genomes: List[Genome]) -> float:
        """Diversity of features used across genomes."""
        all_features: Set[str] = set()
        feature_counts: Dict[str, int] = {}

        for g in genomes:
            features = FactorGenome.get_feature_names(g)
            all_features.update(features)
            for f in features:
                feature_counts[f] = feature_counts.get(f, 0) + 1

        if not all_features:
            return 0.0

        n = len(genomes)
        # Entropy of feature usage
        import math
        entropy = 0.0
        for count in feature_counts.values():
            p = count / n
            entropy -= p * math.log(p) if p > 0 else 0

        max_entropy = math.log(len(all_features)) if all_features else 1
        return entropy / max_entropy if max_entropy > 0 else 0

    def _expression_diversity(self, genomes: List[Genome]) -> float:
        """Diversity of expression structures."""
        hashes = [g.content_hash() for g in genomes if g.root_gene]
        if not hashes:
            return 0.0
        unique = len(set(hashes))
        return unique / len(genomes)

    def _return_profile_diversity(self, genomes: List[Genome]) -> float:
        """Diversity of return profiles (approximated by feature/category spread)."""
        # Placeholder — in production, correlates actual return series
        return self._category_diversity(genomes)

    # ── Enforcement ────────────────────────────────────────

    def is_diverse_enough(self, genomes: List[Genome]) -> bool:
        """Check if population meets diversity thresholds."""
        scores = self.compute_diversity(genomes)
        overall = self.overall_diversity(genomes)

        if overall < self._diversity_target:
            logger.warning("Overall diversity %.2f < target %.2f", overall, self._diversity_target)
            return False

        if scores.get(DiversityDimension.CATEGORY.value, 0) < self._min_category_diversity:
            logger.warning("Category diversity below minimum")
            return False

        return True

    def get_diversity_report(self, genomes: List[Genome]) -> Dict[str, Any]:
        """Generate a detailed diversity report."""
        scores = self.compute_diversity(genomes)
        overall = self.overall_diversity(genomes)

        self._diversity_history.append(scores)

        return {
            "overall": overall,
            "target": self._diversity_target,
            "adequate": self.is_diverse_enough(genomes),
            "dimensions": scores,
            "population_size": len(genomes),
            "category_counts": self._category_counts(genomes),
        }

    def _category_counts(self, genomes: List[Genome]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for g in genomes:
            cat = FactorGenome.classify(g)
            counts[cat.value] = counts.get(cat.value, 0) + 1
        return counts

    @property
    def diversity_target(self) -> float:
        return self._diversity_target
