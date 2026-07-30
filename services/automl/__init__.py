"""AutoML & Alpha Discovery Engine.

Automated model search, hyperparameter optimization, alpha factor
discovery, walk-forward validation, and champion promotion.

Main components:
    - SearchSpace: unified search space (features + models + hyperparams)
    - HyperOptimizer: random/grid/bayesian/tpe search
    - TrialManager: trial lifecycle and parallel execution
    - MultiObjectiveEvaluator: Sharpe, IC, Sortino, Drawdown, Turnover, etc.
    - AlphaDiscovery: automated alpha factor combination discovery
    - FactorCombiner: combinatorial factor search
    - WalkForwardValidator: rolling train/test with time-series awareness
    - TimeSeriesCV: time-preserving cross validation
    - Leaderboard: model ranking and comparison
    - PromotionManager: champion selection and stage promotion
    - AutoMLService: unified orchestrator
"""

from __future__ import annotations

from services.automl.search_space import (
    CategoricalParam,
    ContinuousParam,
    DiscreteParam,
    ModelConfig,
    ParamType,
    SearchSpace,
)
from services.automl.optimizer import (
    HyperOptimizer,
    OptimizationResult,
    SearchStrategy,
)
from services.automl.trial_manager import (
    TrialManager,
    TrialResult,
    TrialStatus,
    TrialTask,
)
from services.automl.evaluator import (
    EvaluationMetric,
    EvaluationResult,
    MultiObjectiveEvaluator,
    ObjectiveConfig,
)
from services.automl.alpha_discovery import (
    AlphaCandidate,
    AlphaDiscovery,
    FactorTemplate,
    Operator,
)
from services.automl.factor_combiner import (
    CombineMethod,
    CombinedFactor,
    FactorCombiner,
)
from services.automl.walk_forward import (
    WalkForwardConfig,
    WalkForwardResult,
    WalkForwardValidator,
    WindowResult,
)
from services.automl.cross_validation import (
    CVConfig,
    CVResult,
    TimeSeriesCV,
)
from services.automl.leaderboard import (
    Leaderboard,
    LeaderboardConfig,
    LeaderboardEntry,
    LeaderboardScope,
    RankMetric,
)
from services.automl.promotion import (
    PromotionConfig,
    PromotionCriteria,
    PromotionManager,
    PromotionResult,
    PromotionStage,
)
from services.automl.service import AutoMLService

__all__ = [
    # Search Space
    "SearchSpace",
    "ParamType",
    "CategoricalParam",
    "ContinuousParam",
    "DiscreteParam",
    "ModelConfig",
    # Optimizer
    "HyperOptimizer",
    "SearchStrategy",
    "OptimizationResult",
    # Trial
    "TrialManager",
    "TrialTask",
    "TrialResult",
    "TrialStatus",
    # Evaluator
    "MultiObjectiveEvaluator",
    "EvaluationResult",
    "EvaluationMetric",
    "ObjectiveConfig",
    # Alpha Discovery
    "AlphaDiscovery",
    "AlphaCandidate",
    "FactorTemplate",
    "Operator",
    # Factor Combiner
    "FactorCombiner",
    "CombinedFactor",
    "CombineMethod",
    # Walk Forward
    "WalkForwardValidator",
    "WalkForwardConfig",
    "WalkForwardResult",
    "WindowResult",
    # Cross Validation
    "TimeSeriesCV",
    "CVConfig",
    "CVResult",
    # Leaderboard
    "Leaderboard",
    "LeaderboardEntry",
    "LeaderboardConfig",
    "LeaderboardScope",
    "RankMetric",
    # Promotion
    "PromotionManager",
    "PromotionConfig",
    "PromotionCriteria",
    "PromotionResult",
    "PromotionStage",
    # Service
    "AutoMLService",
]
