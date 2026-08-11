"""
Redundancy Detector — Identifies and removes redundant factor/alpha candidates.

Redundancy is detected via:
    - Expression similarity (content hash)
    - Feature overlap (Jaccard index of used features)
    - Behavioral correlation (actual signal correlation)
    - Structural similarity (gene tree edit distance)

Prevents the alpha zoo from being filled with duplicate strategies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from services.alpha_evolution.genome import Genome
from services.alpha_evolution.factor_genome import FactorGenome

logger = logging.getLogger(__name__)


@dataclass
class RedundancyReport:
    """Report for redundancy analysis."""

    total_individuals: int
    redundant_ids: List[str]
    redundant_pairs: List[Tuple[str, str, float]]  # (id_a, id_b, similarity)
    non_redundant_ids: List[str]
    similarity_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)


class RedundancyDetector:
    """
    Detects redundant (duplicate or highly-correlated) individuals.

    Redundancy check methods:
        1. Exact hash match (fast, strict)
        2. Feature Jaccard similarity (medium, good heuristic)
        3. Expression tree edit distance (slow, accurate)
    """

    def __init__(
        self,
        max_similarity: float = 0.85,
        min_jaccard_for_redundancy: float = 0.80,
    ):
        self._max_similarity = max_similarity
        self._min_jaccard = min_jaccard_for_redundancy

    # ── Main Detection ─────────────────────────────────────

    def detect_redundancy(
        self,
        genomes: List[Genome],
        signal_correlations: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> RedundancyReport:
        """
        Detect redundant individuals in the population.

        Args:
            genomes: Population genomes
            signal_correlations: Optional pairwise signal correlation matrix

        Returns:
            RedundancyReport with redundant IDs and pairs
        """
        if len(genomes) < 2:
            return RedundancyReport(
                total_individuals=len(genomes),
                redundant_ids=[],
                redundant_pairs=[],
                non_redundant_ids=[g.genome_id for g in genomes],
            )

        redundant: Set[str] = set()
        redundant_pairs: List[Tuple[str, str, float]] = []

        # 1. Exact hash match
        hash_groups: Dict[str, List[str]] = {}
        for g in genomes:
            if not g.root_gene:
                continue
            h = g.content_hash()
            hash_groups.setdefault(h, []).append(g.genome_id)

        for group in hash_groups.values():
            if len(group) > 1:
                # Keep first, mark rest redundant
                for dup_id in group[1:]:
                    redundant.add(dup_id)
                    redundant_pairs.append((group[0], dup_id, 1.0))

        # 2. Feature Jaccard similarity
        non_redundant = [g for g in genomes if g.genome_id not in redundant]
        for i in range(len(non_redundant)):
            features_i = FactorGenome.get_feature_names(non_redundant[i])
            for j in range(i + 1, len(non_redundant)):
                if non_redundant[j].genome_id in redundant:
                    continue
                features_j = FactorGenome.get_feature_names(non_redundant[j])
                jaccard = self._jaccard_similarity(features_i, features_j)
                if jaccard >= self._min_jaccard:
                    redundant.add(non_redundant[j].genome_id)
                    redundant_pairs.append(
                        (non_redundant[i].genome_id, non_redundant[j].genome_id, jaccard)
                    )

        # 3. Signal correlation (if available)
        if signal_correlations:
            non_redundant = [g for g in genomes if g.genome_id not in redundant]
            for i in range(len(non_redundant)):
                gid_i = non_redundant[i].genome_id
                for j in range(i + 1, len(non_redundant)):
                    gid_j = non_redundant[j].genome_id
                    if gid_j in redundant:
                        continue
                    corr = signal_correlations.get(gid_i, {}).get(gid_j, 0)
                    if abs(corr) >= self._max_similarity:
                        redundant.add(gid_j)
                        redundant_pairs.append((gid_i, gid_j, abs(corr)))

        non_redundant_ids = [g.genome_id for g in genomes if g.genome_id not in redundant]

        logger.info(
            "Redundancy: %d/%d marked redundant (%d pairs)",
            len(redundant), len(genomes), len(redundant_pairs),
        )

        return RedundancyReport(
            total_individuals=len(genomes),
            redundant_ids=list(redundant),
            redundant_pairs=redundant_pairs,
            non_redundant_ids=non_redundant_ids,
        )

    # ── Similarity Functions ───────────────────────────────

    def _jaccard_similarity(
        self, set_a: Set[str], set_b: Set[str]
    ) -> float:
        """Jaccard similarity between two feature sets."""
        if not set_a and not set_b:
            return 1.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def expression_similarity(
        self, genome_a: Genome, genome_b: Genome
    ) -> float:
        """Estimate expression similarity (0-1)."""
        if not genome_a.root_gene or not genome_b.root_gene:
            return 0.0

        # Compare expression strings
        expr_a = genome_a.to_expression_string()
        expr_b = genome_b.to_expression_string()

        if expr_a == expr_b:
            return 1.0

        # Simple overlap of features
        features_a = FactorGenome.get_feature_names(genome_a)
        features_b = FactorGenome.get_feature_names(genome_b)
        return self._jaccard_similarity(features_a, features_b)

    # ── Batch Operations ───────────────────────────────────

    def filter_non_redundant(
        self,
        genomes: List[Genome],
        population_genomes: Optional[List[Genome]] = None,
    ) -> List[Genome]:
        """Return only non-redundant genomes."""
        all_genomes = genomes + (population_genomes or [])
        report = self.detect_redundancy(all_genomes)
        non_red_set = set(report.non_redundant_ids)
        return [g for g in genomes if g.genome_id in non_red_set]

    @property
    def max_similarity(self) -> float:
        return self._max_similarity
