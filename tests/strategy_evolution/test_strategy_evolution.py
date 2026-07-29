from services.strategy_evolution import *


def test_strategy_generation():
    agent = StrategyGeneratorAgent()
    result = agent.generate("momentum")
    assert result["strategy"] == "momentum"


def test_strategy_idea_generator():
    gen = StrategyIdeaGenerator()
    result = gen.generate("volatile_market")
    assert result == {"idea": "volatile_market"}


def test_strategy_genome():
    genome = StrategyGenome()
    result = genome.create("momentum_value_blend")
    assert result == {"genome": "momentum_value_blend"}


def test_strategy_generator_agent():
    agent = StrategyGeneratorAgent()
    result = agent.generate({"factors": ["momentum", "volatility"], "universe": "SP500"})
    assert result == {"strategy": {"factors": ["momentum", "volatility"], "universe": "SP500"}}


def test_strategy_mutation():
    engine = StrategyMutationEngine()
    result = engine.mutate({"factor": "MA20", "window": 20})
    assert result == {"mutation": {"factor": "MA20", "window": 20}}


def test_strategy_crossover():
    engine = StrategyCrossoverEngine()
    result = engine.crossover("momentum_strategy", "value_strategy")
    assert result == {"strategy": ("momentum_strategy", "value_strategy")}


def test_fitness_evaluation():
    engine = FitnessEvaluationEngine()
    result = engine.evaluate({"sharpe": 1.5, "return": 0.25})
    assert result == {"fitness": 100}


def test_strategy_selection():
    engine = StrategySelectionEngine()
    strategies = [
        {"name": "Alpha", "score": 95},
        {"name": "Beta", "score": 80},
        {"name": "Gamma", "score": 60},
    ]
    result = engine.select(strategies)
    assert result == [{"name": "Alpha", "score": 95}]


def test_overfit_detection():
    engine = OverfitDetectionEngine()
    result = engine.check({"strategy": "momentum", "in_sample_sharpe": 3.0})
    assert result == {"overfit": False}


def test_strategy_tournament():
    engine = StrategyTournamentEngine()
    strategies = [
        {"name": "Champion", "sharpe": 2.5},
        {"name": "RunnerUp", "sharpe": 2.0},
    ]
    result = engine.compete(strategies)
    assert result == {"winner": {"name": "Champion", "sharpe": 2.5}}


def test_strategy_evolution_memory():
    memory = StrategyEvolutionMemory()
    assert memory.history == []
    memory.save({"generation": 1, "strategy": "momentum_basic"})
    memory.save({"generation": 2, "strategy": "momentum_enhanced"})
    assert len(memory.history) == 2
    assert memory.history[0]["generation"] == 1
    assert memory.history[1]["strategy"] == "momentum_enhanced"


def test_strategy_evolution_service():
    agent = StrategyGeneratorAgent()
    service = StrategyEvolutionService(generator=agent)
    result = service.create("mean_reversion_genome")
    assert result == {"strategy": "mean_reversion_genome"}


def test_full_strategy_evolution_workflow():
    """End-to-end strategy evolution workflow."""
    # 1. Generate strategy idea
    idea_gen = StrategyIdeaGenerator()
    idea = idea_gen.generate("AI_boom_market")
    assert idea["idea"] == "AI_boom_market"

    # 2. Create genome
    genome = StrategyGenome()
    dna = genome.create({"factors": ["momentum", "liquidity"], "entry": "breakout_20d"})
    assert dna["genome"]["factors"] == ["momentum", "liquidity"]

    # 3. Generate strategy
    agent = StrategyGeneratorAgent()
    strategy = agent.generate(dna["genome"])
    assert strategy["strategy"]["factors"] == ["momentum", "liquidity"]

    # 4. Mutate
    mutation = StrategyMutationEngine()
    mutated = mutation.mutate(strategy["strategy"])
    assert mutated["mutation"]["factors"] == ["momentum", "liquidity"]

    # 5. Crossover
    crossover = StrategyCrossoverEngine()
    child = crossover.crossover("momentum_strategy", "liquidity_strategy")
    assert child["strategy"] == ("momentum_strategy", "liquidity_strategy")

    # 6. Evaluate fitness
    fitness = FitnessEvaluationEngine()
    score = fitness.evaluate({"sharpe": 1.8, "max_dd": 0.10})
    assert score["fitness"] == 100

    # 7. Select best strategies
    selection = StrategySelectionEngine()
    pool = [
        {"name": "s1", "fitness": 90},
        {"name": "s2", "fitness": 75},
        {"name": "s3", "fitness": 60},
    ]
    selected = selection.select(pool)
    assert selected[0]["name"] == "s1"

    # 8. Check overfitting
    overfit = OverfitDetectionEngine()
    check = overfit.check({"strategy": "s1", "oos_sharpe": 1.2, "is_sharpe": 1.5})
    assert check["overfit"] is False

    # 9. Run tournament
    tournament = StrategyTournamentEngine()
    contestants = [{"name": "Alpha", "score": 92}, {"name": "Beta", "score": 88}]
    winner = tournament.compete(contestants)
    assert winner["winner"]["name"] == "Alpha"

    # 10. Save evolution history
    memory = StrategyEvolutionMemory()
    memory.save({"gen": 1, "best": "Alpha", "fitness": 92})
    memory.save({"gen": 2, "best": "Alpha_v2", "fitness": 95})
    assert len(memory.history) == 2

    # 11. Evolution service
    service = StrategyEvolutionService(generator=agent)
    new_strategy = service.create({"factors": ["momentum", "value"], "optimized": True})
    assert new_strategy["strategy"]["optimized"] is True
