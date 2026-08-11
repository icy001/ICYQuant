"""
Strategy Evolution — Autonomous strategy generation and portfolio construction.

Capabilities:
    - Strategy genome encoding (entry, exit, sizing, stops)
    - Strategy mutation, crossover, and composition
    - Regime-aware strategy routing
    - Strategy ensemble construction
    - Portfolio genome evolution
    - Multi-objective portfolio optimization
    - Risk budget, volatility, correlation, exposure allocation
    - Position optimization with constraints
    - Portfolio stress testing and drawdown control
    - Allocation and strategy memory with lineage tracking
"""

from services.strategy_evolution.strategy_evolution_platform import StrategyEvolutionPlatform
from services.strategy_evolution.strategy_evolution_gateway import StrategyEvolutionGateway
from services.strategy_evolution.portfolio_builder import PortfolioBuilder
from services.strategy_evolution.portfolio_optimizer import PortfolioOptimizer
from services.strategy_evolution.strategy_generator import StrategyGenerator

__all__ = [
    "StrategyEvolutionPlatform",
    "StrategyEvolutionGateway",
    "PortfolioBuilder",
    "PortfolioOptimizer",
    "StrategyGenerator",
]

__version__ = "0.1.0"
