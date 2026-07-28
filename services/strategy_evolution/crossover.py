"""Crossover Engine – combine two strategy genomes to create hybrids."""

import copy
import random
from typing import Any, Dict, List, Optional

from .genome import GenomeComponent, StrategyGenome


class CrossoverEngine:
    """Combines two strategy genomes to produce hybrid offspring.

    Crossover strategies:
    - Uniform crossover: randomly pick each component from either parent
    - Entry/exit swap: take entry from A, exit from B
    - Filter merge: combine all filters from both parents
    - Weighted blend: blend parameters by a ratio
    """

    CROSSOVER_TYPES = [
        "uniform",
        "entry_exit_swap",
        "filter_merge",
        "weighted_blend",
    ]

    def __init__(self, crossover_rate: float = 0.5, seed: int = 42):
        self._crossover_rate = max(0.0, min(1.0, crossover_rate))
        self._seed = seed
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def combine(self, strategy_a: StrategyGenome,
                strategy_b: StrategyGenome) -> dict:
        """Combine two strategies (legacy interface). Returns simple dict."""
        result = self.crossover(strategy_a, strategy_b)
        return {
            "combined": True,
            "parent_a": strategy_a.name,
            "parent_b": strategy_b.name,
            "offspring": result.to_dict(),
        }

    def crossover(self, genome_a: StrategyGenome,
                  genome_b: StrategyGenome,
                  crossover_type: Optional[str] = None) -> StrategyGenome:
        """Perform crossover between two genomes to produce offspring."""
        if crossover_type and crossover_type not in self.CROSSOVER_TYPES:
            crossover_type = None
        if crossover_type is None:
            crossover_type = self._rng.choice(self.CROSSOVER_TYPES)

        if crossover_type == "uniform":
            offspring = self._uniform_crossover(genome_a, genome_b)
        elif crossover_type == "entry_exit_swap":
            offspring = self._entry_exit_swap(genome_a, genome_b)
        elif crossover_type == "filter_merge":
            offspring = self._filter_merge(genome_a, genome_b)
        elif crossover_type == "weighted_blend":
            offspring = self._weighted_blend(genome_a, genome_b)
        else:
            offspring = self._uniform_crossover(genome_a, genome_b)

        # Update lineage
        offspring.generation = max(genome_a.generation, genome_b.generation) + 1
        offspring.parent_ids = [genome_a.name, genome_b.name]
        offspring.tags.append("crossover")

        return offspring

    def crossover_batch(self, genome_a: StrategyGenome,
                        genome_b: StrategyGenome,
                        count: int = 4) -> List[StrategyGenome]:
        """Generate multiple offspring from two parents using different methods."""
        offspring_list = []
        for i in range(min(count, len(self.CROSSOVER_TYPES))):
            ct = self.CROSSOVER_TYPES[i]
            offspring = self.crossover(genome_a, genome_b, ct)
            offspring.name = f"{genome_a.name}_x_{genome_b.name}_{ct}"
            offspring_list.append(offspring)
        return offspring_list

    # ------------------------------------------------------------------
    # Crossover strategies
    # ------------------------------------------------------------------

    def _uniform_crossover(self, a: StrategyGenome,
                           b: StrategyGenome) -> StrategyGenome:
        """Randomly pick each component from either parent."""
        offspring = StrategyGenome(
            name=f"{a.name}_x_{b.name}",
            description=f"Uniform crossover of {a.name} and {b.name}",
        )

        # Randomly choose entry from A or B
        offspring.entry = self._copy_component(
            a.entry if self._rng.random() < 0.5 else b.entry)

        # Randomly choose exit from A or B
        offspring.exit = self._copy_component(
            a.exit if self._rng.random() < 0.5 else b.exit)

        # Randomly choose risk from A or B
        offspring.risk = self._copy_component(
            a.risk if self._rng.random() < 0.5 else b.risk)

        # Merge filters: pick randomly from both
        all_filters = a.filters + b.filters
        offspring.filters = [
            self._copy_component(f)
            for f in all_filters
            if self._rng.random() < 0.5
        ]

        return offspring

    def _entry_exit_swap(self, a: StrategyGenome,
                         b: StrategyGenome) -> StrategyGenome:
        """Take entry from A and exit from B (or vice versa)."""
        offspring = StrategyGenome(
            name=f"{a.name}_x_{b.name}",
            description=f"Entry from {a.name}, Exit from {b.name}",
        )

        offspring.entry = self._copy_component(a.entry)
        offspring.exit = self._copy_component(b.exit)
        offspring.risk = self._copy_component(a.risk)

        # Merge filters from both
        offspring.filters = [
            self._copy_component(f)
            for f in a.filters + b.filters
        ]

        return offspring

    def _filter_merge(self, a: StrategyGenome,
                      b: StrategyGenome) -> StrategyGenome:
        """Merge all filters from both parents, pick entry/exit/risk from best."""
        offspring = StrategyGenome(
            name=f"{a.name}_x_{b.name}",
            description=f"Merged filters from {a.name} and {b.name}",
        )

        # Use entry from A, exit from B by default
        offspring.entry = self._copy_component(a.entry)
        offspring.exit = self._copy_component(b.exit)
        offspring.risk = self._copy_component(a.risk)

        # Merge all filters, deduplicate by name
        seen = set()
        merged_filters = []
        for f in a.filters + b.filters:
            if f.name not in seen:
                seen.add(f.name)
                merged_filters.append(self._copy_component(f))
        offspring.filters = merged_filters

        return offspring

    def _weighted_blend(self, a: StrategyGenome,
                        b: StrategyGenome) -> StrategyGenome:
        """Blend numerical parameters from both parents."""
        ratio = self._rng.uniform(0.3, 0.7)  # blend ratio for parent A

        offspring = StrategyGenome(
            name=f"{a.name}_x_{b.name}",
            description=f"Weighted blend of {a.name}({ratio:.1f}) and {b.name}({1-ratio:.1f})",
        )

        # Blend entry parameters
        offspring.entry = self._blend_component_params(a.entry, b.entry, ratio)

        # Blend exit parameters
        offspring.exit = self._blend_component_params(a.exit, b.exit, ratio)

        # Blend risk parameters
        offspring.risk = self._blend_component_params(a.risk, b.risk, ratio)

        # Merge filters with blended params where names match
        a_filters = {f.name: f for f in a.filters}
        b_filters = {f.name: f for f in b.filters}
        all_names = set(a_filters.keys()) | set(b_filters.keys())
        for name in all_names:
            if name in a_filters and name in b_filters:
                blended = self._blend_component_params(a_filters[name], b_filters[name], ratio)
                offspring.filters.append(blended)
            elif name in a_filters:
                offspring.filters.append(self._copy_component(a_filters[name]))
            else:
                offspring.filters.append(self._copy_component(b_filters[name]))

        return offspring

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _copy_component(self, comp: GenomeComponent) -> GenomeComponent:
        """Deep-copy a genome component."""
        return GenomeComponent(
            name=comp.name,
            rule_type=comp.rule_type,
            params=dict(comp.params),
            weight=comp.weight,
        )

    def _blend_component_params(self, comp_a: GenomeComponent,
                                comp_b: GenomeComponent,
                                ratio: float) -> GenomeComponent:
        """Blend two components' parameters by ratio."""
        blended = GenomeComponent(
            name=comp_a.name if self._rng.random() < 0.5 else comp_b.name,
            rule_type=comp_a.rule_type if self._rng.random() < 0.5 else comp_b.rule_type,
            weight=round(comp_a.weight * ratio + comp_b.weight * (1 - ratio), 2),
        )

        # Blend numeric params
        all_keys = set(comp_a.params.keys()) | set(comp_b.params.keys())
        for key in all_keys:
            va = comp_a.params.get(key)
            vb = comp_b.params.get(key)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                blended.params[key] = round(va * ratio + vb * (1 - ratio), 2)
            elif va is not None:
                blended.params[key] = va
            elif vb is not None:
                blended.params[key] = vb

        return blended
