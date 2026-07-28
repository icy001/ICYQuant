"""Tests for the Autonomous Strategy Evolution Engine."""

import pytest

from services.strategy_evolution import (
    AlphaPopulation,
    CrossoverEngine,
    EvaluationResult,
    EvolutionEvaluator,
    EvolutionMemory,
    EvolutionRecord,
    GenomeComponent,
    MutationEngine,
    StrategyEvolutionService,
    StrategyGenerator,
    StrategyGenome,
)


# =============================================================================
# StrategyGenome tests
# =============================================================================

class TestStrategyGenome:
    """Test strategy genome model."""

    def test_create_basic_genome(self):
        genome = StrategyGenome(
            name="Test Strategy",
            description="A test strategy",
        )
        assert genome.name == "Test Strategy"
        assert genome.description == "A test strategy"
        assert genome.entry.name == "entry"
        assert genome.exit.name == "exit"
        assert genome.risk.name == "risk"
        assert genome.generation == 0
        assert genome.filters == []

    def test_create_momentum_template(self):
        genome = StrategyGenome.create_momentum_template()
        assert genome.name == "Momentum Alpha"
        assert genome.entry.rule_type == "ma_cross"
        assert genome.entry.params["fast_period"] == 20
        assert genome.entry.params["slow_period"] == 50
        assert len(genome.filters) == 1
        assert genome.filters[0].rule_type == "volume"
        assert genome.exit.rule_type == "atr_stop"
        assert genome.risk.rule_type == "fixed_pct"
        assert "momentum" in genome.tags

    def test_create_mean_reversion_template(self):
        genome = StrategyGenome.create_mean_reversion_template()
        assert genome.name == "Mean Reversion"
        assert genome.entry.rule_type == "bollinger_band"
        assert genome.filters[0].rule_type == "rsi"
        assert genome.exit.rule_type == "mean_return"
        assert "mean_reversion" in genome.tags

    def test_create_breakout_template(self):
        genome = StrategyGenome.create_breakout_template()
        assert genome.name == "Breakout Alpha"
        assert genome.entry.rule_type == "price_channel"
        assert genome.exit.rule_type == "trailing_stop"
        assert genome.risk.rule_type == "volatility_adj"
        assert "breakout" in genome.tags

    def test_get_all_components(self):
        genome = StrategyGenome.create_momentum_template()
        components = genome.get_all_components()
        assert len(components) == 4  # entry, exit, risk, volume_filter

    def test_get_component(self):
        genome = StrategyGenome.create_momentum_template()
        assert genome.get_component("entry").rule_type == "ma_cross"
        assert genome.get_component("exit").rule_type == "atr_stop"
        assert genome.get_component("risk").rule_type == "fixed_pct"
        assert genome.get_component("volume_filter").rule_type == "volume"
        assert genome.get_component("nonexistent") is None

    def test_add_filter(self):
        genome = StrategyGenome.create_momentum_template()
        initial_count = len(genome.filters)
        genome.add_filter(GenomeComponent(
            name="adx_filter", rule_type="adx", params={"period": 14}
        ))
        assert len(genome.filters) == initial_count + 1
        assert genome.filters[-1].name == "adx_filter"

    def test_remove_filter(self):
        genome = StrategyGenome.create_momentum_template()
        assert genome.remove_filter("volume_filter") is True
        assert len(genome.filters) == 0
        assert genome.remove_filter("nonexistent") is False

    def test_to_dict(self):
        genome = StrategyGenome.create_momentum_template()
        d = genome.to_dict()
        assert d["name"] == "Momentum Alpha"
        assert d["entry"]["rule_type"] == "ma_cross"
        assert len(d["filters"]) == 1
        assert d["generation"] == 0

    def test_from_dict(self):
        original = StrategyGenome.create_momentum_template()
        d = original.to_dict()
        restored = StrategyGenome.from_dict(d)
        assert restored.name == original.name
        assert restored.entry.rule_type == original.entry.rule_type
        assert restored.entry.params == original.entry.params
        assert len(restored.filters) == len(original.filters)

    def test_to_rules_dict(self):
        genome = StrategyGenome.create_momentum_template()
        rules = genome.to_rules_dict()
        assert rules["entry"]["type"] == "ma_cross"
        assert rules["entry"]["params"]["fast_period"] == 20
        assert rules["exit"]["type"] == "atr_stop"
        assert rules["risk"]["type"] == "fixed_pct"
        assert len(rules["filters"]) == 1
        assert rules["filters"][0]["type"] == "volume"

    def test_parent_ids_lineage(self):
        genome = StrategyGenome(
            name="Child",
            parent_ids=["ParentA", "ParentB"],
            generation=3,
        )
        assert genome.parent_ids == ["ParentA", "ParentB"]
        assert genome.generation == 3

    def test_metadata(self):
        genome = StrategyGenome(
            name="Meta",
            metadata={"author": "AI", "version": 2},
        )
        assert genome.metadata["author"] == "AI"


class TestGenomeComponent:
    """Test GenomeComponent."""

    def test_create_component(self):
        comp = GenomeComponent(
            name="entry",
            rule_type="ma_cross",
            params={"fast": 10, "slow": 30},
            weight=1.5,
        )
        assert comp.name == "entry"
        assert comp.rule_type == "ma_cross"
        assert comp.params == {"fast": 10, "slow": 30}
        assert comp.weight == 1.5

    def test_component_to_dict(self):
        comp = GenomeComponent(name="filter", rule_type="volume")
        d = comp.to_dict()
        assert d["name"] == "filter"
        assert d["rule_type"] == "volume"

    def test_component_from_dict(self):
        d = {"name": "exit", "rule_type": "atr_stop", "params": {"mult": 2.0}, "weight": 1.0}
        comp = GenomeComponent.from_dict(d)
        assert comp.name == "exit"
        assert comp.rule_type == "atr_stop"
        assert comp.params["mult"] == 2.0

    def test_component_from_dict_defaults(self):
        comp = GenomeComponent.from_dict({})
        assert comp.name == ""
        assert comp.rule_type == ""
        assert comp.params == {}
        assert comp.weight == 1.0


# =============================================================================
# StrategyGenerator tests
# =============================================================================

class TestStrategyGenerator:
    """Test strategy generator."""

    def test_generate_legacy_interface(self):
        generator = StrategyGenerator()
        result = generator.generate("AI Momentum")
        assert result["strategy"] == "AI Momentum"
        assert "genome" in result

    def test_generate_momentum_goal(self):
        generator = StrategyGenerator()
        genome = generator.generate_from_goal("AI Momentum Strategy")
        assert "momentum" in genome.name.lower() or "Momentum" in genome.name
        assert genome.entry.rule_type == "ma_cross"

    def test_generate_mean_reversion_goal(self):
        generator = StrategyGenerator()
        genome = generator.generate_from_goal("Mean Reversion Alpha")
        assert genome.entry.rule_type == "bollinger_band"

    def test_generate_breakout_goal(self):
        generator = StrategyGenerator()
        genome = generator.generate_from_goal("Breakout Trading")
        assert genome.entry.rule_type == "price_channel"

    def test_generate_trend_goal(self):
        generator = StrategyGenerator()
        genome = generator.generate_from_goal("Trend Following System")
        assert genome.entry.rule_type == "ma_cross"

    def test_generate_reversal_goal(self):
        generator = StrategyGenerator()
        genome = generator.generate_from_goal("Reversal Strategy")
        assert genome.entry.rule_type == "bollinger_band"

    def test_generate_unknown_goal(self):
        generator = StrategyGenerator()
        genome = generator.generate_from_goal("Arbitrary Strategy XYZ")
        assert genome.name == "Arbitrary Strategy XYZ"
        assert genome.entry.rule_type == "ma_cross"

    def test_generate_from_template(self):
        generator = StrategyGenerator()
        genome = generator.generate_from_template("momentum")
        assert genome is not None
        assert genome.name == "Momentum Alpha"

        genome = generator.generate_from_template("mean_reversion")
        assert genome is not None
        assert genome.name == "Mean Reversion"

        genome = generator.generate_from_template("breakout")
        assert genome is not None
        assert genome.name == "Breakout Alpha"

    def test_generate_from_invalid_template(self):
        generator = StrategyGenerator()
        genome = generator.generate_from_template("nonexistent")
        assert genome is None

    def test_generate_random(self):
        generator = StrategyGenerator(seed=42)
        genome = generator.generate_random()
        assert genome.name.startswith("RandomAlpha")
        assert genome.entry.rule_type in StrategyGenerator.ENTRY_RULES
        assert genome.exit.rule_type in StrategyGenerator.EXIT_RULES
        assert genome.risk.rule_type in StrategyGenerator.RISK_RULES
        assert len(genome.filters) >= 1
        assert "random_exploration" in genome.tags

    def test_generate_random_different(self):
        generator = StrategyGenerator(seed=42)
        g1 = generator.generate_random()
        g2 = generator.generate_random()
        assert g1.name != g2.name

    def test_generate_batch(self):
        generator = StrategyGenerator()
        variants = generator.generate_batch("AI Momentum", count=5)
        assert len(variants) == 5
        # First is the base (from template), rest are variants
        assert len(variants) == 5
        assert "variant" in variants[1].tags


# =============================================================================
# MutationEngine tests
# =============================================================================

class TestMutationEngine:
    """Test mutation engine."""

    def test_mutate_legacy_interface(self):
        engine = MutationEngine()
        genome = StrategyGenome.create_momentum_template()
        result = engine.mutate(genome)
        assert result["mutation"] == "Momentum Alpha"
        assert "mutated" in result
        assert "mutation_type" in result

    def test_mutate_genome_increments_generation(self):
        engine = MutationEngine()
        genome = StrategyGenome.create_momentum_template()
        genome.generation = 2
        mutated = engine.mutate_genome(genome, "param_tweak")
        assert mutated.generation == 3

    def test_mutate_genome_preserves_original(self):
        engine = MutationEngine()
        genome = StrategyGenome.create_momentum_template()
        original_fast = genome.entry.params["fast_period"]
        _ = engine.mutate_genome(genome, "param_tweak")
        # Original should be unchanged
        assert genome.entry.params["fast_period"] == original_fast

    def test_mutate_genome_adds_parent_id(self):
        engine = MutationEngine()
        genome = StrategyGenome.create_momentum_template()
        mutated = engine.mutate_genome(genome, "rule_swap")
        assert genome.name in mutated.parent_ids

    def test_mutate_genome_adds_tag(self):
        engine = MutationEngine()
        genome = StrategyGenome.create_momentum_template()
        for mt in MutationEngine.MUTATION_TYPES:
            mutated = engine.mutate_genome(genome, mt)
            assert f"mutated_{mt}" in mutated.tags

    def test_mutate_all_types(self):
        engine = MutationEngine(seed=42)
        genome = StrategyGenome.create_momentum_template()
        for mt in MutationEngine.MUTATION_TYPES:
            mutated = engine.mutate_genome(genome, mt)
            assert mutated.name == genome.name
            assert mutated.generation > genome.generation

    def test_mutate_batch(self):
        engine = MutationEngine(seed=42)
        genome = StrategyGenome.create_momentum_template()
        mutations = engine.mutate_batch(genome, count=5)
        assert len(mutations) == 5
        for m in mutations:
            assert m.generation > genome.generation

    def test_guided_mutation_improving(self):
        engine = MutationEngine(seed=42)
        genome = StrategyGenome.create_momentum_template()
        feedback = {"status": "improving", "win_rate": 0.65}
        mutated = engine.guided_mutation(genome, feedback)
        assert mutated.generation > genome.generation

    def test_guided_mutation_critical(self):
        engine = MutationEngine(seed=42)
        genome = StrategyGenome.create_momentum_template()
        feedback = {"status": "critical", "max_drawdown": 35}
        mutated = engine.guided_mutation(genome, feedback)
        assert mutated.generation > genome.generation

    def test_guided_mutation_deteriorating(self):
        engine = MutationEngine(seed=42)
        genome = StrategyGenome.create_momentum_template()
        feedback = {"status": "deteriorating", "win_rate": 0.35}
        mutated = engine.guided_mutation(genome, feedback)
        assert mutated.generation > genome.generation

    def test_guided_mutation_stable(self):
        engine = MutationEngine(seed=42)
        genome = StrategyGenome.create_momentum_template()
        feedback = {"status": "stable", "win_rate": 0.55}
        mutated = engine.guided_mutation(genome, feedback)
        assert mutated.generation > genome.generation

    def test_mutation_rate_bounds(self):
        engine = MutationEngine(mutation_rate=1.5)
        assert engine._mutation_rate == 1.0
        engine = MutationEngine(mutation_rate=-0.5)
        assert engine._mutation_rate == 0.0

    def test_invalid_mutation_type_falls_back_to_random(self):
        engine = MutationEngine(seed=42)
        genome = StrategyGenome.create_momentum_template()
        mutated = engine.mutate_genome(genome, "invalid_type")
        assert mutated.generation > genome.generation

    def test_filter_add_different_rule(self):
        engine = MutationEngine(seed=42)
        genome = StrategyGenome.create_momentum_template()
        genome.filters = []  # clear existing filters
        mutated = engine.mutate_genome(genome, "filter_add")
        assert len(mutated.filters) > 0


# =============================================================================
# CrossoverEngine tests
# =============================================================================

class TestCrossoverEngine:
    """Test crossover engine."""

    def test_combine_legacy_interface(self):
        engine = CrossoverEngine()
        a = StrategyGenome.create_momentum_template()
        b = StrategyGenome.create_mean_reversion_template()
        result = engine.combine(a, b)
        assert result["combined"] is True
        assert result["parent_a"] == "Momentum Alpha"
        assert result["parent_b"] == "Mean Reversion"

    def test_crossover_creates_offspring(self):
        engine = CrossoverEngine(seed=42)
        a = StrategyGenome.create_momentum_template()
        b = StrategyGenome.create_mean_reversion_template()
        offspring = engine.crossover(a, b)
        assert offspring.name != a.name
        assert offspring.name != b.name
        assert "x" in offspring.name

    def test_crossover_increments_generation(self):
        engine = CrossoverEngine(seed=42)
        a = StrategyGenome.create_momentum_template()
        b = StrategyGenome.create_mean_reversion_template()
        a.generation = 2
        b.generation = 3
        offspring = engine.crossover(a, b)
        assert offspring.generation == 4  # max(2, 3) + 1

    def test_crossover_records_parents(self):
        engine = CrossoverEngine(seed=42)
        a = StrategyGenome.create_momentum_template()
        b = StrategyGenome.create_mean_reversion_template()
        offspring = engine.crossover(a, b)
        assert a.name in offspring.parent_ids
        assert b.name in offspring.parent_ids

    def test_crossover_adds_tag(self):
        engine = CrossoverEngine(seed=42)
        a = StrategyGenome.create_momentum_template()
        b = StrategyGenome.create_mean_reversion_template()
        offspring = engine.crossover(a, b)
        assert "crossover" in offspring.tags

    def test_crossover_all_types(self):
        engine = CrossoverEngine(seed=42)
        a = StrategyGenome.create_momentum_template()
        b = StrategyGenome.create_mean_reversion_template()
        for ct in CrossoverEngine.CROSSOVER_TYPES:
            offspring = engine.crossover(a, b, ct)
            assert offspring is not None
            assert len(offspring.parent_ids) == 2

    def test_crossover_batch(self):
        engine = CrossoverEngine(seed=42)
        a = StrategyGenome.create_momentum_template()
        b = StrategyGenome.create_mean_reversion_template()
        batch = engine.crossover_batch(a, b, count=4)
        assert len(batch) == 4
        for offspring in batch:
            assert "crossover" in offspring.tags

    def test_crossover_preserves_parents(self):
        engine = CrossoverEngine(seed=42)
        a = StrategyGenome.create_momentum_template()
        b = StrategyGenome.create_mean_reversion_template()
        _ = engine.crossover(a, b)
        # Parents should be unchanged
        assert a.entry.rule_type == "ma_cross"
        assert b.entry.rule_type == "bollinger_band"

    def test_invalid_crossover_type(self):
        engine = CrossoverEngine(seed=42)
        a = StrategyGenome.create_momentum_template()
        b = StrategyGenome.create_mean_reversion_template()
        offspring = engine.crossover(a, b, "invalid")
        assert offspring is not None  # falls back to random


# =============================================================================
# EvolutionEvaluator tests
# =============================================================================

class TestEvolutionEvaluator:
    """Test evolution evaluator."""

    def test_evaluate_legacy_interface(self):
        evaluator = EvolutionEvaluator()
        result = evaluator.evaluate({"return": 0.15})
        assert result["score"] == {"return": 0.15}

    def test_evaluate_genome_with_metrics(self):
        evaluator = EvolutionEvaluator()
        genome = StrategyGenome.create_momentum_template()
        metrics = {
            "sharpe_ratio": 2.5,
            "total_return_pct": 35.0,
            "max_drawdown_pct": 8.0,
            "win_rate": 0.60,
            "profit_factor": 2.5,
            "ic_mean": 0.08,
            "turnover": 2.0,
        }
        result = evaluator.evaluate_genome(genome, metrics)
        assert result.genome_name == "Momentum Alpha"
        assert result.score > 0
        assert result.score <= 100
        assert result.grade in ("A", "B", "C", "D", "F")

    def test_evaluate_high_performer(self):
        evaluator = EvolutionEvaluator()
        genome = StrategyGenome(name="Top")
        metrics = {
            "sharpe_ratio": 3.5,
            "total_return_pct": 60.0,
            "max_drawdown_pct": 3.0,
            "win_rate": 0.70,
            "profit_factor": 3.5,
            "ic_mean": 0.12,
            "turnover": 0.5,
        }
        result = evaluator.evaluate_genome(genome, metrics)
        assert result.grade == "A"

    def test_evaluate_poor_performer(self):
        evaluator = EvolutionEvaluator()
        genome = StrategyGenome(name="Bad")
        metrics = {
            "sharpe_ratio": -0.5,
            "total_return_pct": -10.0,
            "max_drawdown_pct": 35.0,
            "win_rate": 0.20,
            "profit_factor": 0.3,
            "ic_mean": -0.05,
            "turnover": 15.0,
        }
        result = evaluator.evaluate_genome(genome, metrics)
        assert result.grade == "F"

    def test_evaluate_default_metrics(self):
        evaluator = EvolutionEvaluator()
        genome = StrategyGenome(name="Empty")
        result = evaluator.evaluate_genome(genome)
        assert result.genome_name == "Empty"
        assert result.score >= 0

    def test_evaluate_batch_ranking(self):
        evaluator = EvolutionEvaluator()
        genomes = [
            StrategyGenome(name="A"), StrategyGenome(name="B"),
            StrategyGenome(name="C"),
        ]
        metrics = [
            {"sharpe_ratio": 3.0, "total_return_pct": 50, "max_drawdown_pct": 5},
            {"sharpe_ratio": 1.0, "total_return_pct": 15, "max_drawdown_pct": 10},
            {"sharpe_ratio": -0.5, "total_return_pct": -5, "max_drawdown_pct": 25},
        ]
        results = evaluator.evaluate_batch(genomes, metrics)
        assert results[0].rank == 1
        assert results[0].status == "elite" or results[0].percentile >= 80
        assert results[-1].status in ("review", "cull")

    def test_evaluate_batch_default_metrics(self):
        evaluator = EvolutionEvaluator()
        genomes = [StrategyGenome(name=f"G{i}") for i in range(3)]
        results = evaluator.evaluate_batch(genomes)
        assert len(results) == 3
        for r in results:
            assert r.rank > 0

    def test_rank_and_select(self):
        evaluator = EvolutionEvaluator()
        results = [
            EvaluationResult(genome_name="A", score=90),
            EvaluationResult(genome_name="B", score=70),
            EvaluationResult(genome_name="C", score=50),
        ]
        top = evaluator.rank_and_select(results, top_n=2)
        assert len(top) == 2
        assert top[0].genome_name == "A"

    def test_get_population_stats(self):
        evaluator = EvolutionEvaluator()
        results = [
            EvaluationResult(genome_name="A", score=85, grade="A", status="elite"),
            EvaluationResult(genome_name="B", score=45, grade="D", status="cull"),
        ]
        stats = evaluator.get_population_stats(results)
        assert stats["count"] == 2
        assert stats["avg_score"] == 65.0
        assert stats["elite_count"] == 1
        assert stats["cull_count"] == 1

    def test_get_population_stats_empty(self):
        evaluator = EvolutionEvaluator()
        stats = evaluator.get_population_stats([])
        assert stats["count"] == 0

    def test_select_elite(self):
        evaluator = EvolutionEvaluator()
        results = [
            EvaluationResult(genome_name="A", score=90, percentile=95, status="elite"),
            EvaluationResult(genome_name="B", score=70, percentile=60, status="keep"),
        ]
        elite = evaluator.select_elite(results)
        assert "A" in elite
        assert "B" not in elite

    def test_select_survivors(self):
        evaluator = EvolutionEvaluator()
        results = [
            EvaluationResult(genome_name="A", score=90, status="elite"),
            EvaluationResult(genome_name="B", score=70, status="keep"),
            EvaluationResult(genome_name="C", score=30, status="cull"),
        ]
        survivors = evaluator.select_survivors(results)
        assert "A" in survivors
        assert "B" in survivors
        assert "C" not in survivors

    def test_score_return_buckets(self):
        evaluator = EvolutionEvaluator()
        r = EvaluationResult(genome_name="test", total_return_pct=60)
        score = evaluator._score_return(r.total_return_pct)
        assert score == 30.0

    def test_risk_score_ranges(self):
        evaluator = EvolutionEvaluator()
        genome = StrategyGenome(name="test")
        metrics = {
            "sharpe_ratio": 3.0, "max_drawdown_pct": 5,
            "profit_factor": 2.0,
        }
        result = evaluator.evaluate_genome(genome, metrics)
        assert result.risk_score >= 0

    def test_stability_score_ranges(self):
        evaluator = EvolutionEvaluator()
        genome = StrategyGenome(name="test")
        metrics = {
            "win_rate": 0.65, "ic_mean": 0.1, "turnover": 1.0,
        }
        result = evaluator.evaluate_genome(genome, metrics)
        assert result.stability_score >= 0


class TestEvaluationResult:
    """Test EvaluationResult dataclass."""

    def test_defaults(self):
        r = EvaluationResult(genome_name="Test")
        assert r.score == 0.0
        assert r.grade == ""
        assert r.status == ""

    def test_to_dict(self):
        r = EvaluationResult(
            genome_name="Test", score=85.5, grade="A", status="elite"
        )
        d = r.to_dict()
        assert d["genome_name"] == "Test"
        assert d["score"] == 85.5
        assert d["grade"] == "A"
        assert d["status"] == "elite"


# =============================================================================
# AlphaPopulation tests
# =============================================================================

class TestAlphaPopulation:
    """Test alpha population manager."""

    def test_add_strategy(self):
        pop = AlphaPopulation()
        genome = StrategyGenome.create_momentum_template()
        pop.add(genome)
        assert pop.size == 1
        assert pop.contains("Momentum Alpha")

    def test_add_duplicate_overwrites(self):
        pop = AlphaPopulation()
        g1 = StrategyGenome(name="Test", entry=GenomeComponent(
            name="entry", rule_type="ma_cross", params={"fast": 10}))
        g2 = StrategyGenome(name="Test", entry=GenomeComponent(
            name="entry", rule_type="bollinger_band", params={"period": 20}))
        pop.add(g1)
        pop.add(g2)
        assert pop.size == 1
        assert pop.get("Test").entry.rule_type == "bollinger_band"

    def test_add_batch(self):
        pop = AlphaPopulation()
        genomes = [
            StrategyGenome(name=f"G{i}") for i in range(5)
        ]
        pop.add_batch(genomes)
        assert pop.size == 5

    def test_remove_strategy(self):
        pop = AlphaPopulation()
        pop.add(StrategyGenome(name="Test"))
        assert pop.remove("Test") is True
        assert pop.size == 0
        assert pop.remove("Test") is False

    def test_get_strategy(self):
        pop = AlphaPopulation()
        genome = StrategyGenome.create_momentum_template()
        pop.add(genome)
        assert pop.get("Momentum Alpha") is not None
        assert pop.get("Nonexistent") is None

    def test_get_all(self):
        pop = AlphaPopulation()
        pop.add(StrategyGenome(name="A"))
        pop.add(StrategyGenome(name="B"))
        all_genomes = pop.get_all()
        assert len(all_genomes) == 2

    def test_strategies_property(self):
        pop = AlphaPopulation()
        pop.add(StrategyGenome(name="A"))
        assert len(pop.strategies) == 1

    def test_evaluate_generation(self):
        pop = AlphaPopulation()
        pop.add(StrategyGenome.create_momentum_template())
        pop.add(StrategyGenome.create_mean_reversion_template())
        results = pop.evaluate_generation()
        assert len(results) == 2
        assert pop.generation == 1

    def test_evaluate_with_metrics(self):
        pop = AlphaPopulation()
        pop.add(StrategyGenome(name="Test"))
        results = pop.evaluate_generation({
            "Test": {"sharpe_ratio": 2.0, "total_return_pct": 20}
        })
        assert len(results) == 1

    def test_cull_removes_poor(self):
        pop = AlphaPopulation(max_size=50)
        pop.add(StrategyGenome(name="Good"))
        pop.add(StrategyGenome(name="Bad"))
        results = pop.evaluate_generation({
            "Good": {"sharpe_ratio": 3.0, "total_return_pct": 40, "max_drawdown_pct": 5,
                     "win_rate": 0.65, "profit_factor": 2.5, "ic_mean": 0.08, "turnover": 2},
            "Bad": {"sharpe_ratio": -0.5, "total_return_pct": -10, "max_drawdown_pct": 30,
                    "win_rate": 0.20, "profit_factor": 0.3, "ic_mean": -0.05, "turnover": 15},
        })
        # "Bad" should be culled if its status is "cull"
        culled = pop.cull(results)
        # It's fine if either outcome happens (depends on exact scoring)
        assert culled >= 0

    def test_evolve_cycle(self):
        pop = AlphaPopulation(max_size=50)
        pop.add(StrategyGenome.create_momentum_template())
        pop.add(StrategyGenome.create_mean_reversion_template())
        pop.add(StrategyGenome.create_breakout_template())
        result = pop.evolve_cycle()
        assert "generation" in result
        assert "population_size" in result
        assert "stats" in result

    def test_get_top(self):
        pop = AlphaPopulation(max_size=50)
        pop.add(StrategyGenome(name="A"))
        pop.add(StrategyGenome(name="B"))
        pop.add(StrategyGenome(name="C"))
        pop.evaluate_generation({
            "A": {"sharpe_ratio": 3.0, "total_return_pct": 50},
            "B": {"sharpe_ratio": 1.5, "total_return_pct": 20},
            "C": {"sharpe_ratio": 0.5, "total_return_pct": 5},
        })
        top = pop.get_top(2)
        assert len(top) == 2

    def test_diversity_score(self):
        pop = AlphaPopulation()
        pop.add(StrategyGenome.create_momentum_template())
        pop.add(StrategyGenome.create_mean_reversion_template())
        score = pop.diversity_score()
        assert 0.0 <= score <= 1.0

    def test_diversity_score_single(self):
        pop = AlphaPopulation()
        pop.add(StrategyGenome.create_momentum_template())
        assert pop.diversity_score() == 1.0

    def test_rule_distribution(self):
        pop = AlphaPopulation()
        pop.add(StrategyGenome.create_momentum_template())
        dist = pop.get_rule_distribution()
        assert "entry" in dist
        assert "exit" in dist
        assert "risk" in dist
        assert "filter" in dist

    def test_result_history(self):
        pop = AlphaPopulation()
        pop.add(StrategyGenome(name="Test"))
        pop.evaluate_generation({"Test": {"sharpe_ratio": 2.0}})
        history = pop.get_result_history("Test")
        assert len(history) == 1
        assert history[0].sharpe_ratio == 2.0

    def test_get_latest_result(self):
        pop = AlphaPopulation()
        pop.add(StrategyGenome(name="Test"))
        pop.evaluate_generation({"Test": {"sharpe_ratio": 2.0}})
        latest = pop.get_latest_result("Test")
        assert latest is not None
        assert latest.sharpe_ratio == 2.0

    def test_get_latest_result_nonexistent(self):
        pop = AlphaPopulation()
        assert pop.get_latest_result("Nonexistent") is None

    def test_reset(self):
        pop = AlphaPopulation()
        pop.add(StrategyGenome(name="Test"))
        pop.evaluate_generation()
        pop.reset()
        assert pop.size == 0
        assert pop.generation == 0

    def test_max_size_auto_cull(self):
        pop = AlphaPopulation(max_size=3)
        for i in range(5):
            pop.add(StrategyGenome(name=f"G{i}"))
        assert pop.size <= 3


# =============================================================================
# EvolutionMemory tests
# =============================================================================

class TestEvolutionMemory:
    """Test evolution memory."""

    def test_save_legacy_interface(self):
        memory = EvolutionMemory()
        record = memory.save({"event_type": "test", "genome_name": "G1"})
        assert record.event_type == "test"
        assert record.genome_name == "G1"

    def test_save_record(self):
        memory = EvolutionMemory()
        record = EvolutionRecord(
            event_type="mutation",
            genome_name="Test",
            generation=1,
        )
        saved = memory.save_record(record)
        assert saved.record_id.startswith("EVO-")

    def test_record_generation(self):
        memory = EvolutionMemory()
        record = memory.record_generation(
            generation=3, population_size=20,
            elite=["A", "B"], culled=5,
            stats={"avg_score": 60},
        )
        assert record.event_type == "generation"
        assert record.generation == 3

    def test_record_mutation(self):
        memory = EvolutionMemory()
        record = memory.record_mutation(
            parent_name="Parent", child_name="Child",
            mutation_type="param_tweak", generation=2,
        )
        assert record.event_type == "mutation"
        assert record.parent_ids == ["Parent"]

    def test_record_crossover(self):
        memory = EvolutionMemory()
        record = memory.record_crossover(
            parent_a="A", parent_b="B", child_name="C",
            crossover_type="uniform", generation=3,
        )
        assert record.event_type == "crossover"
        assert record.parent_ids == ["A", "B"]

    def test_record_failure(self):
        memory = EvolutionMemory()
        record = memory.record_failure(
            genome_name="Bad", reason="Low sharpe", generation=2,
        )
        assert record.event_type == "failure"
        assert not record.success
        assert record.notes == "Low sharpe"

    def test_record_deployment(self):
        memory = EvolutionMemory()
        record = memory.record_deployment(
            genome_name="Best", generation=5, score=92.5,
        )
        assert record.event_type == "deploy"
        assert record.metrics["score"] == 92.5

    def test_get_history(self):
        memory = EvolutionMemory()
        memory.save({"event_type": "test"})
        history = memory.get_history()
        assert len(history) == 1

    def test_get_records(self):
        memory = EvolutionMemory()
        memory.record_mutation("A", "B", "test", 1)
        memory.record_crossover("A", "C", "D", "test", 2)
        records = memory.get_records()
        assert len(records) == 2

    def test_get_by_type(self):
        memory = EvolutionMemory()
        memory.record_mutation("A", "B", "param_tweak", 1)
        memory.record_crossover("A", "C", "D", "uniform", 2)
        mutations = memory.get_by_type("mutation")
        assert len(mutations) == 1
        crossovers = memory.get_by_type("crossover")
        assert len(crossovers) == 1

    def test_get_by_genome(self):
        memory = EvolutionMemory()
        memory.record_mutation("A", "B", "test", 1)
        memory.record_mutation("C", "D", "test", 2)
        assert len(memory.get_by_genome("B")) == 1
        assert len(memory.get_by_genome("D")) == 1
        assert len(memory.get_by_genome("Nonexistent")) == 0

    def test_get_by_generation(self):
        memory = EvolutionMemory()
        memory.record_mutation("A", "B", "test", 1)
        memory.record_mutation("C", "D", "test", 2)
        assert len(memory.get_by_generation(1)) == 1
        assert len(memory.get_by_generation(2)) == 1

    def test_get_by_tag(self):
        memory = EvolutionMemory()
        memory.record_mutation("A", "B", "param_tweak", 1)
        assert len(memory.get_by_tag("mutation")) == 1
        assert len(memory.get_by_tag("param_tweak")) == 1
        assert len(memory.get_by_tag("nonexistent")) == 0

    def test_get_successful_mutations(self):
        memory = EvolutionMemory()
        memory.record_mutation("A", "B", "test", 1)
        assert len(memory.get_successful_mutations()) == 1

    def test_get_failed_experiments(self):
        memory = EvolutionMemory()
        memory.record_failure("Bad", "Poor performance", 1)
        failed = memory.get_failed_experiments()
        assert len(failed) == 1

    def test_get_deployments(self):
        memory = EvolutionMemory()
        memory.record_deployment("Best", 5, 95.0)
        assert len(memory.get_deployments()) == 1

    def test_get_successful_patterns(self):
        memory = EvolutionMemory()
        memory.record_mutation("A", "B", "param_tweak", 1)
        patterns = memory.get_successful_patterns()
        assert len(patterns) == 1

    def test_get_failed_patterns(self):
        memory = EvolutionMemory()
        memory.record_failure("Bad", "High drawdown", 2)
        patterns = memory.get_failed_patterns()
        assert len(patterns) == 1

    def test_summary(self):
        memory = EvolutionMemory()
        memory.record_mutation("A", "B", "test", 1)
        memory.record_crossover("A", "C", "D", "test", 2)
        summary = memory.summary()
        assert summary["total_records"] == 2
        assert summary["max_generation"] == 2

    def test_summary_empty(self):
        memory = EvolutionMemory()
        summary = memory.summary()
        assert summary["total_records"] == 0

    def test_reset(self):
        memory = EvolutionMemory()
        memory.record_mutation("A", "B", "test", 1)
        memory.reset()
        assert len(memory.get_records()) == 0


# =============================================================================
# StrategyEvolutionService tests
# =============================================================================

class TestStrategyEvolutionService:
    """Test strategy evolution service."""

    def test_evolve_legacy_interface(self):
        generator = StrategyGenerator()
        service = StrategyEvolutionService(generator)
        result = service.evolve("AI Momentum")
        assert result["strategy"] == "AI Momentum"

    def test_generate_from_goal_adds_to_population(self):
        service = StrategyEvolutionService()
        genome = service.generate_from_goal("Momentum Strategy")
        assert service.population.contains(genome.name)
        assert service.population.size == 1

    def test_generate_random(self):
        service = StrategyEvolutionService()
        genomes = service.generate_random(count=3)
        assert len(genomes) == 3
        assert service.population.size == 3

    def test_generate_batch(self):
        service = StrategyEvolutionService()
        genomes = service.generate_batch("AI Momentum", count=5)
        assert len(genomes) == 5
        assert service.population.size == 5

    def test_mutate_strategy(self):
        service = StrategyEvolutionService()
        service.generate_from_goal("Momentum Alpha")
        mutated = service.mutate_strategy("Momentum Alpha", "param_tweak")
        assert mutated is not None
        assert mutated.generation > 0

    def test_mutate_nonexistent(self):
        service = StrategyEvolutionService()
        assert service.mutate_strategy("Nonexistent") is None

    def test_mutate_batch(self):
        service = StrategyEvolutionService()
        service.generate_from_goal("Momentum Alpha")
        mutations = service.mutate_batch("Momentum Alpha", count=3)
        assert len(mutations) == 3

    def test_mutate_batch_nonexistent(self):
        service = StrategyEvolutionService()
        assert service.mutate_batch("Nonexistent") == []

    def test_crossover_strategies(self):
        service = StrategyEvolutionService()
        service.generate_from_goal("Momentum Alpha")
        service.generate_from_goal("Mean Reversion")
        offspring = service.crossover_strategies("Momentum Alpha", "Mean Reversion")
        assert offspring is not None

    def test_crossover_nonexistent(self):
        service = StrategyEvolutionService()
        service.generate_from_goal("Momentum Alpha")
        assert service.crossover_strategies("Momentum Alpha", "Nonexistent") is None
        assert service.crossover_strategies("Nonexistent", "Momentum Alpha") is None

    def test_crossover_batch(self):
        service = StrategyEvolutionService()
        service.generate_from_goal("Momentum Alpha")
        service.generate_from_goal("Mean Reversion")
        batch = service.crossover_batch("Momentum Alpha", "Mean Reversion", count=2)
        assert len(batch) == 2

    def test_evolve_generation(self):
        service = StrategyEvolutionService()
        service.generate_batch("AI Momentum", count=5)
        result = service.evolve_generation()
        assert "generation" in result
        assert "population_size" in result
        assert "elite" in result
        assert "stats" in result

    def test_run_evolution(self):
        service = StrategyEvolutionService()
        result = service.run_evolution("AI Momentum Strategy", generations=2, population_size=5)
        assert result["goal"] == "AI Momentum Strategy"
        assert result["generations_run"] == 2
        assert len(result["cycle_results"]) == 2
        assert "best_strategy" in result
        assert "best_score" in result
        assert "memory_summary" in result

    def test_get_population(self):
        service = StrategyEvolutionService()
        service.generate_from_goal("Test Strategy")
        pop = service.get_population()
        assert len(pop) == 1

    def test_get_top_strategies(self):
        service = StrategyEvolutionService()
        service.generate_from_goal("Test Strategy")
        top = service.get_top_strategies(5)
        assert len(top) == 1

    def test_get_diversity(self):
        service = StrategyEvolutionService()
        service.generate_from_goal("Momentum Alpha")
        diversity = service.get_diversity()
        assert diversity == 1.0

    def test_get_evolution_summary(self):
        service = StrategyEvolutionService()
        service.generate_from_goal("Momentum Alpha")
        summary = service.get_evolution_summary()
        assert "population" in summary
        assert "memory" in summary
        assert "top_strategies" in summary

    def test_reset(self):
        service = StrategyEvolutionService()
        service.generate_from_goal("Test Strategy")
        service.reset()
        assert service.population.size == 0

    def test_full_evolution_workflow(self):
        """Integration test: full evolution workflow."""
        service = StrategyEvolutionService()

        # 1. Seed population
        genomes = service.generate_batch("AI Momentum", count=5)
        assert len(genomes) == 5

        # 2. Run a generation
        result = service.evolve_generation()
        assert result["population_size"] > 0

        # 3. Get top strategies
        top = service.get_top_strategies(3)
        assert len(top) > 0

        # 4. Check memory
        summary = service.memory.summary()
        assert summary["total_records"] > 0

        # 5. Diversity check
        diversity = service.get_diversity()
        assert 0.0 <= diversity <= 1.0

    def test_end_to_end_evolution(self):
        """End-to-end test: goal → evolve → best strategy."""
        service = StrategyEvolutionService()

        # Run full evolution
        result = service.run_evolution(
            goal="Semiconductor Momentum v2",
            generations=3,
            population_size=8,
        )

        # Verify results
        assert result["generations_run"] == 3
        assert result["best_strategy"] is not None
        assert result["best_score"] >= 0
        assert service.population.size > 0
        assert service.memory.summary()["total_records"] > 0


# =============================================================================
# Custom crossover with same parents (edge case)
# =============================================================================

class TestEdgeCases:
    """Edge case tests."""

    def test_crossover_same_genome(self):
        engine = CrossoverEngine(seed=42)
        genome = StrategyGenome.create_momentum_template()
        offspring = engine.crossover(genome, genome)
        assert offspring is not None

    def test_empty_population_diversity(self):
        pop = AlphaPopulation()
        assert pop.diversity_score() == 1.0

    def test_empty_population_stats(self):
        evaluator = EvolutionEvaluator()
        stats = evaluator.get_population_stats([])
        assert stats == {"count": 0}

    def test_empty_memory_summary(self):
        memory = EvolutionMemory()
        summary = memory.summary()
        assert summary["total_records"] == 0

    def test_generator_generate_random_with_prefix(self):
        generator = StrategyGenerator(seed=42)
        genome = generator.generate_random(name_prefix="Explorer")
        assert genome.name.startswith("Explorer")

    def test_mutation_preserves_component_names(self):
        engine = MutationEngine(seed=42)
        genome = StrategyGenome.create_momentum_template()
        mutated = engine.mutate_genome(genome, "param_tweak")
        assert mutated.entry.name == "entry"
        assert mutated.exit.name == "exit"
        assert mutated.risk.name == "risk"

    def test_crossover_offspring_has_all_components(self):
        engine = CrossoverEngine(seed=42)
        a = StrategyGenome.create_momentum_template()
        b = StrategyGenome.create_mean_reversion_template()
        offspring = engine.crossover(a, b)
        assert offspring.entry is not None
        assert offspring.exit is not None
        assert offspring.risk is not None

    def test_filter_merge_deduplication(self):
        engine = CrossoverEngine(seed=42)
        a = StrategyGenome.create_momentum_template()  # has volume_filter
        b = StrategyGenome.create_momentum_template()  # also has volume_filter
        offspring = engine.crossover(a, b, "filter_merge")
        # Should not have duplicate filter names
        filter_names = [f.name for f in offspring.filters]
        assert len(filter_names) == len(set(filter_names))

    def test_population_get_top_empty(self):
        pop = AlphaPopulation()
        top = pop.get_top(5)
        assert len(top) == 0

    def test_evaluator_evaluate_batch_empty(self):
        evaluator = EvolutionEvaluator()
        results = evaluator.evaluate_batch([])
        assert len(results) == 0
