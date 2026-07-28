"""Alpha Population Manager – manage the evolving strategy pool."""

from typing import Any, Dict, List, Optional

from .genome import StrategyGenome
from .evaluator import EvaluationResult, EvolutionEvaluator


class AlphaPopulation:
    """Manages a population of strategy genomes through evolution cycles.

    Responsibilities:
    - Maintain the strategy pool (active genomes)
    - Track population history across generations
    - Support add, remove, select, and cull operations
    - Compute population diversity metrics
    """

    def __init__(self, max_size: int = 100):
        self._strategies: Dict[str, StrategyGenome] = {}
        self._results: Dict[str, List[EvaluationResult]] = {}  # genome_name -> history
        self._generation: int = 0
        self._max_size = max_size
        self._evaluator = EvolutionEvaluator()

    # ------------------------------------------------------------------
    # Population management
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self._strategies)

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def strategies(self) -> list:
        """List of strategy genomes in the population."""
        return list(self._strategies.values())

    def add(self, strategy: StrategyGenome) -> None:
        """Add a strategy to the population."""
        if len(self._strategies) >= self._max_size:
            # Remove lowest-scored strategy if at capacity
            self._cull_lowest()
        self._strategies[strategy.name] = strategy

    def add_batch(self, strategies: List[StrategyGenome]) -> None:
        """Add multiple strategies to the population."""
        for s in strategies:
            self.add(s)

    def remove(self, name: str) -> bool:
        """Remove a strategy by name. Returns True if removed."""
        if name in self._strategies:
            del self._strategies[name]
            return True
        return False

    def get(self, name: str) -> Optional[StrategyGenome]:
        """Get a strategy genome by name."""
        return self._strategies.get(name)

    def get_all(self) -> List[StrategyGenome]:
        """Get all strategy genomes."""
        return list(self._strategies.values())

    def get_top(self, n: int = 10) -> List[StrategyGenome]:
        """Get top N strategies by latest evaluation score."""
        scored = []
        for name, genome in self._strategies.items():
            latest = self.get_latest_result(name)
            score = latest.score if latest else 0.0
            scored.append((score, genome))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [g for _, g in scored[:n]]

    def contains(self, name: str) -> bool:
        """Check if a strategy exists in the population."""
        return name in self._strategies

    # ------------------------------------------------------------------
    # Evolution cycle
    # ------------------------------------------------------------------

    def evaluate_generation(self, metrics_map: Optional[Dict[str, dict]] = None
                            ) -> List[EvaluationResult]:
        """Evaluate all strategies in the current generation.

        Args:
            metrics_map: dict mapping genome_name -> backtest metrics
        """
        metrics_map = metrics_map or {}
        genomes = list(self._strategies.values())
        metrics_list = [metrics_map.get(g.name, {}) for g in genomes]
        results = self._evaluator.evaluate_batch(genomes, metrics_list)

        # Store results in history
        for r in results:
            if r.genome_name not in self._results:
                self._results[r.genome_name] = []
            self._results[r.genome_name].append(r)

        self._generation += 1
        return results

    def select_survivors(self, results: List[EvaluationResult]) -> List[str]:
        """Select strategies that survive to the next generation."""
        return self._evaluator.select_survivors(results)

    def cull(self, results: List[EvaluationResult]) -> int:
        """Remove poor-performing strategies from the population.

        Returns number of strategies removed.
        """
        to_cull = [r.genome_name for r in results if r.status == "cull"]
        count = 0
        for name in to_cull:
            if self.remove(name):
                count += 1
        return count

    def evolve_cycle(self, metrics_map: Optional[Dict[str, dict]] = None
                     ) -> dict:
        """Run one complete evolution cycle: evaluate → select → cull.

        Returns a summary of the cycle.
        """
        # 1. Evaluate
        results = self.evaluate_generation(metrics_map)

        # 2. Get stats
        stats = self._evaluator.get_population_stats(results)

        # 3. Cull poor performers
        culled = self.cull(results)

        # 4. Select elite for next round
        elite = self._evaluator.select_elite(results)

        return {
            "generation": self._generation,
            "population_size": self.size,
            "culled": culled,
            "elite_count": len(elite),
            "elite": elite,
            "stats": stats,
        }

    # ------------------------------------------------------------------
    # Result history
    # ------------------------------------------------------------------

    def get_result_history(self, genome_name: str) -> List[EvaluationResult]:
        """Get evaluation history for a specific strategy."""
        return self._results.get(genome_name, [])

    def get_latest_result(self, genome_name: str) -> Optional[EvaluationResult]:
        """Get the most recent evaluation result for a strategy."""
        history = self._results.get(genome_name, [])
        return history[-1] if history else None

    def get_all_results(self) -> Dict[str, List[EvaluationResult]]:
        """Get all evaluation results."""
        return dict(self._results)

    # ------------------------------------------------------------------
    # Diversity metrics
    # ------------------------------------------------------------------

    def diversity_score(self) -> float:
        """Compute population diversity based on rule type distribution.

        Returns a score from 0.0 (all identical) to 1.0 (maximally diverse).
        """
        if self.size < 2:
            return 1.0

        entry_types = {}
        exit_types = {}
        risk_types = {}

        for genome in self._strategies.values():
            et = genome.entry.rule_type
            entry_types[et] = entry_types.get(et, 0) + 1

            xt = genome.exit.rule_type
            exit_types[xt] = exit_types.get(xt, 0) + 1

            rt = genome.risk.rule_type
            risk_types[rt] = risk_types.get(rt, 0) + 1

        n = self.size
        entry_div = len(entry_types) / n
        exit_div = len(exit_types) / n
        risk_div = len(risk_types) / n

        return round((entry_div + exit_div + risk_div) / 3, 3)

    def get_rule_distribution(self) -> dict:
        """Get distribution of rule types in the population."""
        entry_dist: Dict[str, int] = {}
        exit_dist: Dict[str, int] = {}
        risk_dist: Dict[str, int] = {}
        filter_dist: Dict[str, int] = {}

        for genome in self._strategies.values():
            entry_dist[genome.entry.rule_type] = \
                entry_dist.get(genome.entry.rule_type, 0) + 1
            exit_dist[genome.exit.rule_type] = \
                exit_dist.get(genome.exit.rule_type, 0) + 1
            risk_dist[genome.risk.rule_type] = \
                risk_dist.get(genome.risk.rule_type, 0) + 1
            for f in genome.filters:
                filter_dist[f.rule_type] = filter_dist.get(f.rule_type, 0) + 1

        return {
            "entry": entry_dist,
            "exit": exit_dist,
            "risk": risk_dist,
            "filter": filter_dist,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cull_lowest(self) -> None:
        """Remove the lowest-scored strategy to make room."""
        if not self._strategies:
            return
        worst_name = None
        worst_score = float("inf")
        for name in self._strategies:
            latest = self.get_latest_result(name)
            score = latest.score if latest else 0.0
            if score < worst_score:
                worst_score = score
                worst_name = name
        if worst_name:
            self.remove(worst_name)

    def reset(self) -> None:
        """Reset the population."""
        self._strategies.clear()
        self._results.clear()
        self._generation = 0
