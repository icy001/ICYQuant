"""Multi-Agent Reinforcement Learning Trading System.

Provides:
- RL Trading Environment: market simulation for RL training
- Trading Simulator: realistic trade execution with costs
- State Encoder: market features → state vectors
- Action Space: discrete and continuous action spaces
- Reward Engine: multi-objective reward shaping
- Policy Network: neural network policy models
- RL Trainer: PPO/SAC/DQN/A2C training loop
- Agent Self-Play: multi-agent competitive learning
- Market Regime Adapter: dynamic strategy switching
- Portfolio Optimizer: RL-based portfolio allocation
"""

from .environment import (
    RLTradingEnvironment, EnvironmentConfig, MarketState,
    EnvironmentStep, EnvironmentEpisode,
)
from .simulator import (
    TradingSimulator, SimulatorConfig, TradeResult, MarketImpactModel,
)
from .reward_engine import (
    RewardEngine, RewardConfig, RewardComponents, RewardType,
)
from .state_encoder import (
    StateEncoder, EncoderConfig, MarketEmbedding, EncodedState,
)
from .action_space import (
    ActionSpace, DiscreteActionSpace, ContinuousActionSpace,
    ActionType, ActionConfig,
)
from .policy_network import (
    PolicyNetwork, PolicyConfig, ActorCriticNetwork, NetworkType,
)
from .trainer import (
    RLTrainer, TrainerConfig, TrainingResult, AlgorithmType,
    TrainingEpisode, TrainingMetrics,
)
from .evaluator import (
    RLEvaluator, EvaluatorConfig, EvaluationResult, EvaluationMetrics,
)
from .agent_selfplay import (
    SelfPlayManager, SelfPlayConfig, SelfPlayAgent, CompetitionResult,
    AgentStrategy,
)
from .regime_adapter import (
    RegimeAdapter, RegimeConfig, MarketRegime, RegimePolicy,
)
from .portfolio_optimizer import (
    RLPortfolioOptimizer, OptimizerConfig, PortfolioAllocation,
    AllocationResult,
)
from .service import (
    RLService, RLServiceConfig, RLServiceStatus, TrainingJob,
)
from .api.rl_api import RLAPI, APIResponse

__all__ = [
    # Environment
    "RLTradingEnvironment", "EnvironmentConfig", "MarketState",
    "EnvironmentStep", "EnvironmentEpisode",
    # Simulator
    "TradingSimulator", "SimulatorConfig", "TradeResult", "MarketImpactModel",
    # Reward
    "RewardEngine", "RewardConfig", "RewardComponents", "RewardType",
    # State Encoder
    "StateEncoder", "EncoderConfig", "MarketEmbedding", "EncodedState",
    # Action Space
    "ActionSpace", "DiscreteActionSpace", "ContinuousActionSpace",
    "ActionType", "ActionConfig",
    # Policy Network
    "PolicyNetwork", "PolicyConfig", "ActorCriticNetwork", "NetworkType",
    # Trainer
    "RLTrainer", "TrainerConfig", "TrainingResult", "AlgorithmType",
    "TrainingEpisode", "TrainingMetrics",
    # Evaluator
    "RLEvaluator", "EvaluatorConfig", "EvaluationResult", "EvaluationMetrics",
    # Self-Play
    "SelfPlayManager", "SelfPlayConfig", "SelfPlayAgent", "CompetitionResult",
    "AgentStrategy",
    # Regime Adapter
    "RegimeAdapter", "RegimeConfig", "MarketRegime", "RegimePolicy",
    # Portfolio Optimizer
    "RLPortfolioOptimizer", "OptimizerConfig", "PortfolioAllocation",
    "AllocationResult",
    # Service & API
    "RLService", "RLServiceConfig", "RLServiceStatus", "TrainingJob",
    "RLAPI", "APIResponse",
]
