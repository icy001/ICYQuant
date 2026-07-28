"""Strategy Evolution Service – unified API for autonomous strategy evolution.

Orchestrates the complete evolution loop:
    Generate → Evaluate → Select → Mutate/Crossover → Repeat
"""

from typing import Any, Dict, List, Optional

from .crossover import CrossoverEngine
from .evaluator import EvaluationResult, EvolutionEvaluator
from .generator import StrategyGenerator
from .genome import StrategyGenome
from .memory import EvolutionMemory
from .mutation import MutationEngine
from .population import AlphaPopulation


class StrategyEvolutionService:
    """Unified service for autonomous strategy evolution.

    Orchestrates:
    - Strategy generation from goals/templates/random exploration
    - Evolution cycles (evaluate → select → mutate/crossover)
    - Alpha population management
    - Evolution memory (tracking lineage, successes, failures)
    """

    def __init__(
        self,
        generator: Optional[StrategyGenerator] = None,
        mutation_engine: Optional[MutationEngine] = None,
        crossover_engine: Optional[CrossoverEngine] = None,
        evaluator: Optional[EvolutionEvaluator] = None,
        population: Optional[AlphaPopulation] = None,
        memory: Optional[EvolutionMemory] = None,
    ):
        self.generator = generator or StrategyGenerator()
        self.mutation = mutation_engine or MutationEngine()
        self.crossover = crossover_engine or CrossoverEngine()
        self.evaluator = evaluator or EvolutionEvaluator()
        self.population = population or AlphaPopulation()
        self.memory = memory or EvolutionMemory()

    # ------------------------------------------------------------------
    # Legacy API
    # ------------------------------------------------------------------

    def evolve(self, goal: str) -> dict:
        """Evolve strategies from a goal (legacy interface).

        Returns a simple dict for backward compatibility.
        """
        result = self.generator.generate(goal)
        return result

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate_from_goal(self, goal: str) -> StrategyGenome:
        """Generate a strategy from a research goal."""
        genome = self.generator.generate_from_goal(goal)
        self.population.add(genome)
        return genome

    def generate_random(self, name_prefix: str = "RandomAlpha",
                        count: int = 1) -> List[StrategyGenome]:
        """Generate random exploration strategies."""
        genomes = [self.generator.generate_random(name_prefix)
                   for _ in range(count)]
        self.population.add_batch(genomes)
        return genomes

    def generate_batch(self, goal: str, count: int = 5) -> List[StrategyGenome]:
        """Generate multiple strategy variants from a goal."""
        genomes = self.generator.generate_batch(goal, count)
        self.population.add_batch(genomes)
        return genomes

    # ------------------------------------------------------------------
    # Evolution operations
    # ------------------------------------------------------------------

    def mutate_strategy(self, name: str,
                        mutation_type: Optional[str] = None) -> Optional[StrategyGenome]:
        """Mutate a strategy in the population."""
        genome = self.population.get(name)
        if genome is None:
            return None

        mutated = self.mutation.mutate_genome(genome, mutation_type)
        self.population.add(mutated)

        self.memory.record_mutation(
            parent_name=name,
            child_name=mutated.name,
            mutation_type=mutation_type or "random",
            generation=mutated.generation,
        )

        return mutated

    def mutate_batch(self, name: str, count: int = 5) -> List[StrategyGenome]:
        """Generate multiple mutations from a single strategy."""
        genome = self.population.get(name)
        if genome is None:
            return []

        mutations = self.mutation.mutate_batch(genome, count)
        self.population.add_batch(mutations)

        for m in mutations:
            self.memory.record_mutation(
                parent_name=name,
                child_name=m.name,
                mutation_type="batch",
                generation=m.generation,
            )

        return mutations

    def crossover_strategies(self, name_a: str, name_b: str,
                             crossover_type: Optional[str] = None
                             ) -> Optional[StrategyGenome]:
        """Cross two strategies to create a hybrid."""
        genome_a = self.population.get(name_a)
        genome_b = self.population.get(name_b)
        if genome_a is None or genome_b is None:
            return None

        offspring = self.crossover.crossover(genome_a, genome_b, crossover_type)
        self.population.add(offspring)

        self.memory.record_crossover(
            parent_a=name_a,
            parent_b=name_b,
            child_name=offspring.name,
            crossover_type=crossover_type or "random",
            generation=offspring.generation,
        )

        return offspring

    def crossover_batch(self, name_a: str, name_b: str,
                        count: int = 4) -> List[StrategyGenome]:
        """Generate multiple offspring from two parents."""
        genome_a = self.population.get(name_a)
        genome_b = self.population.get(name_b)
        if genome_a is None or genome_b is None:
            return []

        offspring_list = self.crossover.crossover_batch(genome_a, genome_b, count)
        self.population.add_batch(offspring_list)

        for o in offspring_list:
            self.memory.record_crossover(
                parent_a=name_a,
                parent_b=name_b,
                child_name=o.name,
                crossover_type="batch",
                generation=o.generation,
            )

        return offspring_list

    # ------------------------------------------------------------------
    # Evolution cycle
    # ------------------------------------------------------------------

    def evolve_generation(self, metrics_map: Optional[Dict[str, dict]] = None
                          ) -> dict:
        """Run one evolution cycle: evaluate → cull → mutate elites."""
        # 1. Evaluate current generation
        results = self.population.evaluate_generation(metrics_map)

        # 2. Cull poor performers
        culled = self.population.cull(results)

        # 3. Select elite for reproduction
        elite_names = self.evaluator.select_elite(results, max_count=5)

        # 4. Mutate elites to create next generation
        new_genomes = []
        for name in elite_names:
            mutations = self.mutate_batch(name, count=2)
            new_genomes.extend(mutations)

        # 5. Crossover among elites
        for i in range(len(elite_names)):
            for j in range(i + 1, min(i + 2, len(elite_names))):
                offspring = self.crossover_strategies(elite_names[i], elite_names[j])
                if offspring:
                    new_genomes.append(offspring)

        # 6. Record generation event
        self.memory.record_generation(
            generation=self.population.generation,
            population_size=self.population.size,
            elite=elite_names,
            culled=culled,
            stats=self.evaluator.get_population_stats(results),
        )

        return {
            "generation": self.population.generation,
            "population_size": self.population.size,
            "culled": culled,
            "elite": elite_names,
            "new_genomes": [g.name for g in new_genomes],
            "stats": self.evaluator.get_population_stats(results),
        }

    def run_evolution(self, goal: str, generations: int = 3,
                      population_size: int = 10) -> dict:
        """Run a full evolution process for a given goal.

        This is the main autonomous evolution loop:
        1. Seed initial population from the goal
        2. Run N generations of evaluate → select → mutate/crossover
        3. Return the best strategy found
        """
        cycle_results = []

        # Seed initial population
        base = self.generate_from_goal(goal)
        variants = self.generator.generate_batch(goal, count=population_size - 1)
        for v in variants:
            self.population.add(v)

        self.memory.save({
            "event_type": "evolution_start",
            "genome_name": goal,
            "generation": 0,
            "description": f"Started evolution for: {goal} with {population_size} seeds",
        })

        # Evolution loop
        for gen in range(generations):
            # Simulate metrics for demo/testing (production would use real backtest)
            metrics = self._simulate_metrics()

            result = self.evolve_generation(metrics)
            cycle_results.append(result)

        # Find best strategy
        all_results = self.population.get_all_results()
        best_name = None
        best_score = -float("inf")
        for name, history in all_results.items():
            if history and history[-1].score > best_score:
                best_score = history[-1].score
                best_name = name

        best_genome = self.population.get(best_name) if best_name else None

        return {
            "goal": goal,
            "generations_run": generations,
            "cycle_results": cycle_results,
            "best_strategy": best_genome.to_dict() if best_genome else None,
            "best_score": best_score,
            "population_size": self.population.size,
            "memory_summary": self.memory.summary(),
        }

    # ------------------------------------------------------------------
    # Query & Reporting
    # ------------------------------------------------------------------

    def get_population(self) -> List[dict]:
        """Get current population as dicts."""
        return [g.to_dict() for g in self.population.get_all()]

    def get_top_strategies(self, n: int = 10) -> List[dict]:
        """Get top N strategies by score."""
        top = self.population.get_top(n)
        results = []
        for g in top:
            latest = self.population.get_latest_result(g.name)
            d = g.to_dict()
            d["latest_score"] = latest.score if latest else 0.0
            d["latest_grade"] = latest.grade if latest else "N/A"
            results.append(d)
        return results

    def get_diversity(self) -> float:
        """Get population diversity score."""
        return self.population.diversity_score()

    def get_evolution_summary(self) -> dict:
        """Get a comprehensive evolution summary."""
        return {
            "population": {
                "size": self.population.size,
                "generation": self.population.generation,
                "diversity": self.population.diversity_score(),
                "rule_distribution": self.population.get_rule_distribution(),
            },
            "memory": self.memory.summary(),
            "top_strategies": self.get_top_strategies(5),
        }

    def reset(self) -> None:
        """Reset the service state."""
        self.population.reset()
        self.memory.reset()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _simulate_metrics(self) -> Dict[str, dict]:
        """Generate simulated backtest metrics for demo purposes.

        In production, this would be replaced by actual backtest results.
        """
        import random
        rng = random.Random(42)
        metrics = {}
        for genome in self.population.get_all():
            metrics[genome.name] = {
                "sharpe_ratio": round(rng.uniform(-0.5, 3.5), 2),
                "total_return_pct": round(rng.uniform(-10, 60), 1),
                "max_drawdown_pct": round(rng.uniform(2, 35), 1),
                "win_rate": round(rng.uniform(0.25, 0.75), 2),
                "profit_factor": round(rng.uniform(0.5, 4.0), 2),
                "ic_mean": round(rng.uniform(-0.05, 0.15), 3),
                "turnover": round(rng.uniform(0.5, 12.0), 1),
            }
        return metrics
