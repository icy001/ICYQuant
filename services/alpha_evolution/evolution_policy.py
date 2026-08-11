"""Evolution Policy — Governance policy for autonomous evolution."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EvolutionPolicyLevel(Enum):
    RESTRICTED = 1
    GUIDED = 2
    STANDARD = 3
    AGGRESSIVE = 4


@dataclass
class EvolutionPolicy:
    """Governs the boundaries of autonomous evolution."""

    level: EvolutionPolicyLevel = EvolutionPolicyLevel.STANDARD
    max_population: int = 10000
    max_generations: int = 500
    max_mutation_rate: float = 0.50
    max_crossover_rate: float = 0.50
    min_fitness_threshold: float = 0.20
    max_redundancy_correlation: float = 0.85
    diversity_target: float = 0.40
    novelty_weight: float = 0.10
    max_backtests_per_generation: int = 500
    max_compute_hours_per_run: float = 72.0
    early_stopping_generations: int = 20
    require_approval_for_promotion: bool = True
    max_promoted_per_run: int = 50
    allowed_factor_categories: List[str] = field(default_factory=lambda: [
        "momentum", "value", "quality", "volatility", "volume", "growth"
    ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.name,
            "max_population": self.max_population,
            "max_generations": self.max_generations,
            "max_mutation_rate": self.max_mutation_rate,
            "max_crossover_rate": self.max_crossover_rate,
            "min_fitness_threshold": self.min_fitness_threshold,
            "diversity_target": self.diversity_target,
            "max_backtests_per_generation": self.max_backtests_per_generation,
            "require_approval": self.require_approval_for_promotion,
        }
