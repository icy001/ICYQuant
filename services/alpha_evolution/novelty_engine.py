"""
Novelty Engine — Rewards novel/unusual factor and alpha expressions.

Novelty is measured by:
    - Expression distance (edit distance between genome trees)
    - Feature distance (how different are the input features)
    - Behavior distance (correlation of output signals)
    - Historical novelty (has this been tried before)

Novelty scoring boosts exploration and prevents local optima.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from services.alpha_evolution.genome import Genome
from services.alpha_evolution.factor_genome import FactorGenome

logger = logging.getLogger(__name__)


class NoveltyEngine:
    """
    Computes novelty scores to reward exploration of new factor/alpha expressions.

    Dimensions:
        - Expression novelty: how different is the genome tree?
        - Feature novelty: using rare feature combinations?
        - Behavioral novelty: producing different signals?
        - Historical novelty: not tried before?
    """

    def __init__(
        self,
        novelty_weight: float = 0.10,
        archive_size: int = 1000,
        novelty_threshold: float = 0.30,
    ):
        self._novelty_weight = novelty_weight
        self._archive_size = archive_size
        self._novelty_threshold = novelty_threshold
        self._behavior_archive: List[str] = []  # content hashes
        self._feature_archive: List[Set[str]] = []

    # ── Novelty Scoring ────────────────────────────────────

    def score_novelty(
        self,
        genome: Genome,
        population_genomes: Optional[List[Genome]] = None,
    ) -> float:
        """
        Compute novelty score for a genome.

        Returns 0.0 (common) to 1.0 (highly novel).
        """
        if not genome.root_gene:
            return 0.0

        scores = []

        # Expression novelty (based on content hash uniqueness)
        content_hash = genome.content_hash()
        if self._behavior_archive:
            expr_score = 1.0 if content_hash not in self._behavior_archive else 0.0
        else:
            expr_score = 0.5
        scores.append(expr_score * 0.30)

        # Feature novelty (rare feature usage)
        features = FactorGenome.get_feature_names(genome)
        feature_score = self._feature_novelty(features)
        scores.append(feature_score * 0.30)

        # Population novelty (distance from current population)
        if population_genomes:
            pop_score = self._population_novelty(genome, population_genomes)
            scores.append(pop_score * 0.40)
        else:
            scores.append(0.5 * 0.40)

        # Archive to memory
        self._archive(content_hash, features)

        return sum(scores)

    def score_batch(
        self,
        genomes: List[Genome],
        population_genomes: Optional[List[Genome]] = None,
    ) -> Dict[str, float]:
        """Compute novelty scores for a batch of genomes."""
        return {
            g.genome_id: self.score_novelty(g, population_genomes)
            for g in genomes
        }

    # ── Sub-scores ─────────────────────────────────────────

    def _feature_novelty(self, features: Set[str]) -> float:
        """Score based on how rarely these features have been used."""
        if not features:
            return 0.0
        if not self._feature_archive:
            return 1.0

        # Count how many archived individuals used each feature
        feature_frequencies = {}
        for archived_features in self._feature_archive:
            for f in features:
                if f in archived_features:
                    feature_frequencies[f] = feature_frequencies.get(f, 0) + 1

        n_archived = max(len(self._feature_archive), 1)
        avg_frequency = sum(
            feature_frequencies.get(f, 0) / n_archived
            for f in features
        ) / max(len(features), 1)

        # Novel = low frequency
        return 1.0 - min(avg_frequency, 1.0)

    def _population_novelty(
        self,
        genome: Genome,
        population: List[Genome],
    ) -> float:
        """Score based on distance from current population."""
        my_hash = genome.content_hash()
        pop_hashes = [g.content_hash() for g in population if g.root_gene]

        if not pop_hashes:
            return 1.0

        # Count unique hashes (simplified distance measure)
        unique_hashes = set(pop_hashes)
        if my_hash not in unique_hashes:
            return 1.0

        # If identical, score inversely proportional to duplicates
        duplicates = sum(1 for h in pop_hashes if h == my_hash)
        return 1.0 / max(duplicates, 1)

    # ── Archive Management ─────────────────────────────────

    def _archive(self, content_hash: str, features: Set[str]) -> None:
        """Archive genome for future novelty comparison."""
        if content_hash not in self._behavior_archive:
            self._behavior_archive.append(content_hash)
        self._feature_archive.append(features)

        # Prune archive
        if len(self._behavior_archive) > self._archive_size:
            self._behavior_archive = self._behavior_archive[-self._archive_size:]
        if len(self._feature_archive) > self._archive_size:
            self._feature_archive = self._feature_archive[-self._archive_size:]

    def is_novel_enough(self, novelty_score: float) -> bool:
        """Check if novelty score meets threshold."""
        return novelty_score >= self._novelty_threshold

    def get_stats(self) -> Dict[str, Any]:
        return {
            "archive_size": len(self._behavior_archive),
            "max_archive": self._archive_size,
            "novelty_threshold": self._novelty_threshold,
        }

    def clear_archive(self) -> None:
        """Clear the novelty archive."""
        self._behavior_archive.clear()
        self._feature_archive.clear()
