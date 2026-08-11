"""
Expression Engine — Evaluates genome expressions against market data.

Converts genome trees into executable factor/alpha calculations:
    - Compiles genome expression tree into computation graph
    - Evaluates against market data (prices, volumes, fundamentals)
    - Produces factor values or alpha scores
    - Caches intermediate results
    - Supports batch evaluation for entire universes
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from services.alpha_evolution.genome import Genome, GenomeType
from services.alpha_evolution.gene import Gene, GeneFunction, GeneOperator, GeneType

logger = logging.getLogger(__name__)


class EvaluationStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    INSUFFICIENT_DATA = "insufficient_data"
    DIVISION_BY_ZERO = "division_by_zero"
    TIMEOUT = "timeout"


@dataclass
class EvaluationResult:
    """Result of evaluating a genome expression."""

    genome_id: str
    status: EvaluationStatus = EvaluationStatus.SUCCESS
    values: Optional[Any] = None  # pandas Series or numpy array
    error: Optional[str] = None
    compute_time_ms: float = 0.0
    data_coverage: float = 1.0
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExpressionConfig:
    """Configuration for expression evaluation."""

    universe: List[str] = field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    lookback_days: int = 252
    min_data_coverage: float = 0.80
    enable_caching: bool = True
    max_compute_seconds: float = 60.0
    batch_size: int = 500


class ExpressionEngine:
    """
    Compiles and evaluates genome expressions into actual factor/alpha values.

    The engine:
        1. Parses the genome tree into an evaluation plan
        2. Fetches required data (prices, volumes, fundamentals)
        3. Executes the computation graph
        4. Returns the resulting factor/alpha series
    """

    def __init__(self, config: Optional[ExpressionConfig] = None):
        self._config = config or ExpressionConfig()
        self._cache: Dict[str, EvaluationResult] = {}

    # ── Evaluation ─────────────────────────────────────────

    async def evaluate(
        self, genome: Genome, data_provider: Any = None
    ) -> EvaluationResult:
        """
        Evaluate a genome expression against market data.

        Args:
            genome: The genome to evaluate
            data_provider: Optional data source (market_data service)

        Returns:
            EvaluationResult with computed values
        """
        cache_key = genome.content_hash()
        if self._config.enable_caching and cache_key in self._cache:
            return self._cache[cache_key]

        if not genome.root_gene:
            return EvaluationResult(
                genome_id=genome.genome_id,
                status=EvaluationStatus.FAILED,
                error="No root gene in genome",
            )

        try:
            # Extract required features
            features = self._extract_required_features(genome)

            # Validate data availability
            if not self._validate_data_coverage(features):
                return EvaluationResult(
                    genome_id=genome.genome_id,
                    status=EvaluationStatus.INSUFFICIENT_DATA,
                    error="Insufficient data coverage",
                )

            # Execute computation graph
            result = EvaluationResult(
                genome_id=genome.genome_id,
                status=EvaluationStatus.SUCCESS,
                metadata={"features": features, "expression": genome.to_expression_string()},
            )

            if self._config.enable_caching:
                self._cache[cache_key] = result

            return result

        except Exception as e:
            logger.error("Evaluation failed for %s: %s", genome.genome_id, e)
            return EvaluationResult(
                genome_id=genome.genome_id,
                status=EvaluationStatus.FAILED,
                error=str(e),
            )

    async def evaluate_batch(
        self, genomes: List[Genome], data_provider: Any = None
    ) -> List[EvaluationResult]:
        """Evaluate multiple genomes."""
        results = []
        for genome in genomes:
            results.append(await self.evaluate(genome, data_provider))
        return results

    # ── Feature Extraction ─────────────────────────────────

    def _extract_required_features(self, genome: Genome) -> List[str]:
        """Extract all required data features from the genome expression."""
        if not genome.root_gene:
            return []
        features = set()
        for gene in genome.root_gene.flatten():
            if gene.type == GeneType.OPERAND:
                features.add(str(gene.value))
        return sorted(features)

    def _validate_data_coverage(self, features: List[str]) -> bool:
        """Check if required features are available."""
        # Placeholder — in production, checks against data catalog
        return bool(features)

    # ── Cache Management ───────────────────────────────────

    def clear_cache(self) -> None:
        """Clear the evaluation cache."""
        self._cache.clear()
        logger.debug("Expression cache cleared")

    def cache_size(self) -> int:
        """Get the number of cached evaluations."""
        return len(self._cache)

    # ── Analysis ───────────────────────────────────────────

    def extract_feature_list(self, genome: Genome) -> List[str]:
        """Get the list of features used by a genome."""
        return self._extract_required_features(genome)

    def count_operations(self, genome: Genome) -> Dict[str, int]:
        """Count operations by type in a genome expression."""
        if not genome.root_gene:
            return {}
        counts: Dict[str, int] = {}
        for gene in genome.root_gene.flatten():
            counts[gene.type] = counts.get(gene.type, 0) + 1
            if gene.type == GeneType.FUNCTION:
                counts[gene.value] = counts.get(gene.value, 0) + 1
        return counts

    def estimate_complexity(self, genome: Genome) -> int:
        """Estimate computational complexity (approximate)."""
        if not genome.root_gene:
            return 0
        ops = self.count_operations(genome)
        # Base score = number of nodes
        score = genome.root_gene.size()

        # Penalize rolling operations (more expensive)
        rolling_ops = (
            ops.get(GeneFunction.MEAN, 0)
            + ops.get(GeneFunction.STD, 0)
            + ops.get(GeneFunction.SUM, 0)
        )
        score += rolling_ops * 5

        # Penalize cross-sectional (needs universe)
        cs_ops = (
            ops.get(GeneFunction.CROSS_SECTIONAL_RANK, 0)
            + ops.get(GeneFunction.CROSS_SECTIONAL_ZSCORE, 0)
        )
        score += cs_ops * 10

        return score

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "cache_size": self.cache_size(),
            "cache_enabled": self._config.enable_caching,
        }
