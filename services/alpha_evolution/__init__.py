"""
Alpha Evolution Engine — Autonomous factor and alpha evolution platform.

Capabilities:
    - Factor & Alpha genome encoding
    - Mutation, crossover, and gene expression
    - Multi-objective fitness evaluation
    - Pareto frontier optimization
    - Diversity & novelty preservation
    - Robustness validation (OOS, walk-forward, regime)
    - Decay, turnover, capacity, transaction cost analysis
    - Evolution memory & failure memory
    - Generation tracking & lineage
"""

from services.alpha_evolution.evolution_platform import EvolutionPlatform
from services.alpha_evolution.evolution_gateway import EvolutionGateway
from services.alpha_evolution.population_manager import PopulationManager
from services.alpha_evolution.fitness_engine import FitnessEngine
from services.alpha_evolution.selection_engine import SelectionEngine
from services.alpha_evolution.mutation_engine import MutationEngine
from services.alpha_evolution.crossover_engine import CrossoverEngine

__all__ = [
    "EvolutionPlatform",
    "EvolutionGateway",
    "PopulationManager",
    "FitnessEngine",
    "SelectionEngine",
    "MutationEngine",
    "CrossoverEngine",
]

__version__ = "0.1.0"
