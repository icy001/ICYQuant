# Autonomous Strategy Evolution Engine

## Responsibility

The Strategy Evolution Engine enables ICYQuant to automatically discover, generate,
optimize, and iterate trading strategies through evolutionary computation.

Provides:

- Strategy Genome abstraction (DNA model for strategies)
- Strategy Generation (from goals, templates, or random exploration)
- Mutation Engine (param tweaks, rule swaps, filter add/remove, weight adjust)
- Crossover Engine (uniform, entry/exit swap, filter merge, weighted blend)
- Evolution Evaluator (multi-dimensional scoring: return, risk-adjusted, stability)
- Alpha Population Manager (strategy pool with cull/select cycles)
- Evolution Memory (lineage tracking, failure/success pattern storage)

## Architecture

```
Research Goal
    ↓
Strategy Generation
    ↓
Strategy Pool (Alpha Population)
    ↓
Backtest Evaluation
    ↓
Select Best Candidates
    ↓
Mutation / Crossover
    ↓
New Generation
    ↓
Repeat (Evolution Loop)
```

## Module Structure

```
services/strategy_evolution/
├── genome.py      - StrategyGenome, GenomeComponent
├── generator.py   - StrategyGenerator
├── mutation.py    - MutationEngine
├── crossover.py   - CrossoverEngine
├── evaluator.py   - EvolutionEvaluator, EvaluationResult
├── population.py  - AlphaPopulation
├── memory.py      - EvolutionMemory, EvolutionRecord
└── service.py     - StrategyEvolutionService (orchestrator)
```

## Key Concepts

### Strategy Genome

A strategy is decomposed into evolvable components:
- **Entry** (e.g., ma_cross, bollinger_band, price_channel)
- **Filters** (e.g., volume, rsi, atr, sentiment)
- **Exit** (e.g., atr_stop, trailing_stop, target_pct)
- **Risk** (e.g., fixed_pct, volatility_adj, kelly)

### Evolution Scoring

```
Strategy Score = Return Score (0-30) + Risk-Adjusted Score (0-40) + Stability Score (0-30)
```

Grading:
- A: >= 80
- B: >= 65
- C: >= 50
- D: >= 35
- F: < 35

### Population Management

- **elite**: top 20% percentile
- **keep**: 50-80% percentile
- **review**: 20-50% percentile
- **cull**: bottom 20% percentile

## Usage

```python
from services.strategy_evolution import StrategyEvolutionService

service = StrategyEvolutionService()

# Generate strategies
genome = service.generate_from_goal("AI Momentum Strategy")

# Mutate
mutated = service.mutate_strategy(genome.name, "param_tweak")

# Crossover
offspring = service.crossover_strategies("StrategyA", "StrategyB")

# Run full evolution
result = service.run_evolution(
    goal="Semiconductor Momentum",
    generations=5,
    population_size=10,
)

print(f"Best strategy: {result['best_score']}")
```

## Future Upgrade

Production Features:

- Genetic Programming for strategy discovery
- Reinforcement Learning strategy search
- LLM-based strategy generation (natural language → code)
- Automated Alpha Mining from market data
- Self-Optimizing Quant Models
- Distributed evolution (parallel fitness evaluation)
- Co-evolution of strategies with market regimes
- Multi-objective optimization (Pareto front)
