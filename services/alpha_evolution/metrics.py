"""
Evolution Metrics — Prometheus metrics for alpha evolution.

icyquant_evolution_generations_total
icyquant_evolution_population_size
icyquant_factor_mutations_total
icyquant_alpha_mutations_total
icyquant_factor_crossovers_total
icyquant_alpha_crossovers_total
icyquant_alpha_candidates_total
icyquant_alpha_promotions_total
icyquant_alpha_rejections_total
icyquant_alpha_redundancy_total
icyquant_alpha_novelty_score
icyquant_alpha_fitness_score
icyquant_evolution_compute_cost
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict

logger = logging.getLogger(__name__)


@dataclass
class EvolutionMetrics:
    """Container for all evolution metrics."""

    generations_total: int = 0
    population_size: int = 0
    factor_mutations_total: int = 0
    alpha_mutations_total: int = 0
    factor_crossovers_total: int = 0
    alpha_crossovers_total: int = 0
    alpha_candidates_total: int = 0
    alpha_promotions_total: int = 0
    alpha_rejections_total: int = 0
    alpha_redundancy_total: int = 0
    avg_novelty_score: float = 0.0
    avg_fitness_score: float = 0.0
    compute_cost: float = 0.0


class EvolutionMetricsCollector:
    """Collects evolution metrics for monitoring and observability."""

    def __init__(self):
        self._metrics = EvolutionMetrics()

    def increment_generation(self, delta: int = 1) -> None:
        self._metrics.generations_total += delta

    def set_population_size(self, size: int) -> None:
        self._metrics.population_size = size

    def record_mutation(self, count: int = 1) -> None:
        self._metrics.factor_mutations_total += count

    def record_crossover(self, count: int = 1) -> None:
        self._metrics.factor_crossovers_total += count

    def record_candidate(self, count: int = 1) -> None:
        self._metrics.alpha_candidates_total += count

    def record_promotion(self, count: int = 1) -> None:
        self._metrics.alpha_promotions_total += count

    def record_rejection(self, count: int = 1) -> None:
        self._metrics.alpha_rejections_total += count

    def record_redundancy(self, count: int = 1) -> None:
        self._metrics.alpha_redundancy_total += count

    def set_avg_novelty(self, score: float) -> None:
        self._metrics.avg_novelty_score = score

    def set_avg_fitness(self, score: float) -> None:
        self._metrics.avg_fitness_score = score

    def add_compute_cost(self, hours: float) -> None:
        self._metrics.compute_cost += hours

    def snapshot(self) -> Dict[str, Any]:
        return {
            "evolution_generations_total": self._metrics.generations_total,
            "evolution_population_size": self._metrics.population_size,
            "factor_mutations_total": self._metrics.factor_mutations_total,
            "alpha_mutations_total": self._metrics.alpha_mutations_total,
            "factor_crossovers_total": self._metrics.factor_crossovers_total,
            "alpha_crossovers_total": self._metrics.alpha_crossovers_total,
            "alpha_candidates_total": self._metrics.alpha_candidates_total,
            "alpha_promotions_total": self._metrics.alpha_promotions_total,
            "alpha_rejections_total": self._metrics.alpha_rejections_total,
            "alpha_redundancy_total": self._metrics.alpha_redundancy_total,
            "avg_novelty_score": self._metrics.avg_novelty_score,
            "avg_fitness_score": self._metrics.avg_fitness_score,
            "compute_cost_hours": self._metrics.compute_cost,
        }

    def reset(self) -> None:
        self._metrics = EvolutionMetrics()
