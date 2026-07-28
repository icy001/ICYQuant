"""Mutation Engine – apply evolutionary mutations to strategy genomes."""

import copy
import random
from typing import Any, Dict, List, Optional

from .genome import GenomeComponent, StrategyGenome


class MutationEngine:
    """Applies genetic mutations to strategy genomes.

    Mutation types:
    - Param mutation: tweak numerical parameters (fast_period, threshold, etc.)
    - Rule swap: replace one rule type with another (e.g., ma_cross → bollinger_band)
    - Filter add/remove: add or remove a filter component
    - Weight adjustment: change component weights
    - Structure mutation: larger structural changes

    Each mutation preserves the original genome and creates a mutated copy,
    tracking the lineage.
    """

    MUTATION_TYPES = [
        "param_tweak",
        "rule_swap",
        "filter_add",
        "filter_remove",
        "weight_adjust",
    ]

    # Valid replacements for each component category
    ENTRY_ALTERNATIVES = ["ma_cross", "bollinger_band", "price_channel", "rsi_signal",
                          "macd_signal", "volume_breakout", "support_resistance"]
    FILTER_ALTERNATIVES = ["volume", "rsi", "atr", "adx", "sentiment", "correlation",
                           "market_regime", "sector_momentum"]
    EXIT_ALTERNATIVES = ["atr_stop", "trailing_stop", "mean_return", "time_stop",
                         "target_pct", "signal_reverse", "volatility_stop"]
    RISK_ALTERNATIVES = ["fixed_pct", "volatility_adj", "kelly", "equal_weight",
                         "risk_parity"]

    def __init__(self, mutation_rate: float = 0.3, seed: int = 42):
        self._mutation_rate = max(0.0, min(1.0, mutation_rate))
        self._seed = seed
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mutate(self, strategy: StrategyGenome,
               mutation_type: Optional[str] = None) -> dict:
        """Mutate a strategy (legacy interface). Returns simple dict."""
        mutated = self.mutate_genome(strategy, mutation_type)
        return {"mutation": strategy.name, "mutated": mutated.to_dict(),
                "mutation_type": mutation_type or "random"}

    def mutate_genome(self, genome: StrategyGenome,
                      mutation_type: Optional[str] = None) -> StrategyGenome:
        """Apply a mutation to a strategy genome, returning a new genome."""
        mutated = self._copy_genome(genome)

        if mutation_type and mutation_type not in self.MUTATION_TYPES:
            mutation_type = None

        if mutation_type is None:
            mutation_type = self._rng.choice(self.MUTATION_TYPES)

        if mutation_type == "param_tweak":
            self._param_tweak(mutated)
        elif mutation_type == "rule_swap":
            self._rule_swap(mutated)
        elif mutation_type == "filter_add":
            self._filter_add(mutated)
        elif mutation_type == "filter_remove":
            self._filter_remove(mutated)
        elif mutation_type == "weight_adjust":
            self._weight_adjust(mutated)

        # Update lineage
        mutated.generation = genome.generation + 1
        mutated.parent_ids = [genome.name] + list(genome.parent_ids)
        mutated.tags.append(f"mutated_{mutation_type}")

        return mutated

    def mutate_batch(self, genome: StrategyGenome,
                     count: int = 5) -> List[StrategyGenome]:
        """Generate multiple mutations from a single genome."""
        mutations = []
        for i in range(count):
            mt = self.MUTATION_TYPES[i % len(self.MUTATION_TYPES)]
            mutated = self.mutate_genome(genome, mt)
            mutated.name = f"{genome.name}_mut{i+1}"
            mutations.append(mutated)
        return mutations

    def guided_mutation(self, genome: StrategyGenome,
                        feedback: dict) -> StrategyGenome:
        """Apply mutation guided by performance feedback.

        feedback dict should contain keys like:
        - win_rate, profit_factor, max_drawdown, sharpe_estimate
        - status ("improving", "stable", "deteriorating", "critical")
        """
        status = feedback.get("status", "stable")

        if status == "improving":
            # Small tweaks – strategy is working
            mutated = self._copy_genome(genome)
            self._param_tweak(mutated)
            return self._finalize_mutation(mutated, genome, "guided_improving")
        elif status == "critical":
            # Major overhaul – swap rules
            mutated = self._copy_genome(genome)
            self._rule_swap(mutated)
            return self._finalize_mutation(mutated, genome, "guided_critical")
        elif status == "deteriorating":
            # Try adding a new filter
            mutated = self._copy_genome(genome)
            self._filter_add(mutated)
            return self._finalize_mutation(mutated, genome, "guided_deteriorating")
        else:
            # Stable – random mutation
            return self.mutate_genome(genome)

    def _finalize_mutation(self, mutated: StrategyGenome,
                           original: StrategyGenome,
                           tag: str) -> StrategyGenome:
        """Set generation, parent_ids, and tags on a mutated genome."""
        mutated.generation = original.generation + 1
        mutated.parent_ids = [original.name] + list(original.parent_ids)
        mutated.tags.append(f"mutated_{tag}")
        return mutated

    # ------------------------------------------------------------------
    # Mutation operations
    # ------------------------------------------------------------------

    def _param_tweak(self, genome: StrategyGenome) -> StrategyGenome:
        """Tweak numerical parameters on components."""
        components = genome.get_all_components()
        for comp in components:
            for key, value in list(comp.params.items()):
                if isinstance(value, (int, float)):
                    if isinstance(value, int):
                        delta = self._rng.choice([-2, -1, 1, 2])
                        comp.params[key] = max(1, value + delta)
                    else:
                        delta = self._rng.uniform(-0.3, 0.3) * value
                        comp.params[key] = round(value + delta, 2)
        return genome

    def _rule_swap(self, genome: StrategyGenome) -> StrategyGenome:
        """Swap one component's rule type."""
        target = self._rng.choice(["entry", "exit", "risk"])
        alternatives = {
            "entry": self.ENTRY_ALTERNATIVES,
            "exit": self.EXIT_ALTERNATIVES,
            "risk": self.RISK_ALTERNATIVES,
        }

        comp = getattr(genome, target)
        alts = [a for a in alternatives[target] if a != comp.rule_type]
        if alts:
            comp.rule_type = self._rng.choice(alts)
            # Reset params for new rule type
            comp.params = {"mutated": True, "original_type": comp.rule_type}

        return genome

    def _filter_add(self, genome: StrategyGenome) -> StrategyGenome:
        """Add a new filter component."""
        existing_names = {f.name for f in genome.filters}
        available = [f for f in self.FILTER_ALTERNATIVES
                     if f"{f}_filter" not in existing_names]
        if available:
            new_rule = self._rng.choice(available)
            genome.add_filter(GenomeComponent(
                name=f"{new_rule}_filter",
                rule_type=new_rule,
                params={"threshold": round(self._rng.uniform(0.3, 0.8), 2)},
            ))
        return genome

    def _filter_remove(self, genome: StrategyGenome) -> StrategyGenome:
        """Remove a filter component if present."""
        if len(genome.filters) > 0:
            target = self._rng.choice(genome.filters)
            genome.remove_filter(target.name)
        return genome

    def _weight_adjust(self, genome: StrategyGenome) -> StrategyGenome:
        """Adjust component weights."""
        for comp in genome.get_all_components():
            delta = self._rng.uniform(-0.2, 0.2)
            comp.weight = round(max(0.1, min(3.0, comp.weight + delta)), 2)
        return genome

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _copy_genome(self, genome: StrategyGenome) -> StrategyGenome:
        """Deep-copy a genome for mutation."""
        return StrategyGenome(
            name=genome.name,
            description=genome.description,
            entry=GenomeComponent(
                name=genome.entry.name,
                rule_type=genome.entry.rule_type,
                params=dict(genome.entry.params),
                weight=genome.entry.weight,
            ),
            filters=[GenomeComponent(
                name=f.name,
                rule_type=f.rule_type,
                params=dict(f.params),
                weight=f.weight,
            ) for f in genome.filters],
            exit=GenomeComponent(
                name=genome.exit.name,
                rule_type=genome.exit.rule_type,
                params=dict(genome.exit.params),
                weight=genome.exit.weight,
            ),
            risk=GenomeComponent(
                name=genome.risk.name,
                rule_type=genome.risk.rule_type,
                params=dict(genome.risk.params),
                weight=genome.risk.weight,
            ),
            generation=genome.generation,
            parent_ids=list(genome.parent_ids),
            tags=list(genome.tags),
            metadata=dict(genome.metadata),
        )
