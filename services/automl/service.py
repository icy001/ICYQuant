"""AutoML Service — unified orchestrator.

Provides a single entry point for all AutoML operations:
search, optimize, evaluate, rank, and promote.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from services.automl.search_space import SearchSpace
from services.automl.optimizer import HyperOptimizer, OptimizationResult, SearchStrategy
from services.automl.trial_manager import TrialManager, TrialResult, TrialTask
from services.automl.evaluator import EvaluationResult, MultiObjectiveEvaluator, ObjectiveConfig
from services.automl.alpha_discovery import AlphaCandidate, AlphaDiscovery, FactorTemplate
from services.automl.factor_combiner import CombineMethod, CombinedFactor, FactorCombiner
from services.automl.walk_forward import WalkForwardConfig, WalkForwardResult, WalkForwardValidator
from services.automl.cross_validation import CVConfig, CVResult, TimeSeriesCV
from services.automl.leaderboard import Leaderboard, LeaderboardConfig, LeaderboardEntry, LeaderboardScope, RankMetric
from services.automl.promotion import PromotionConfig, PromotionManager, PromotionResult, PromotionStage


class AutoMLService:
    """Unified AutoML orchestrator.

    Composes all AutoML sub-systems: search space, optimizer,
    evaluator, alpha discovery, walk-forward, leaderboard,
    and promotion.
    """

    def __init__(
        self,
        search_space: Optional[SearchSpace] = None,
        strategy: SearchStrategy = SearchStrategy.RANDOM,
        seed: int = 42,
    ) -> None:
        self.search_space = search_space or SearchSpace()
        self.optimizer = HyperOptimizer(self.search_space, strategy, seed)
        self.trial_manager = TrialManager()
        self.evaluator = MultiObjectiveEvaluator()
        self.alpha_discovery = AlphaDiscovery(seed)
        self.factor_combiner = FactorCombiner()
        self.walk_forward = WalkForwardValidator()
        self.time_series_cv = TimeSeriesCV()
        self.leaderboard = Leaderboard()
        self.promotion = PromotionManager()

    # ---- optimization ----

    def optimize(
        self,
        objective_fn: Callable[[Dict[str, Any]], float],
        n_trials: Optional[int] = None,
        strategy: Optional[SearchStrategy] = None,
        maximize: bool = True,
    ) -> OptimizationResult:
        """Run hyperparameter optimization."""
        if strategy:
            self.optimizer.strategy = strategy
        return self.optimizer.optimize(objective_fn, n_trials, maximize=maximize)

    def run_trials(
        self,
        objective_fn: Callable[[Dict[str, Any]], float],
        configs: List[Dict[str, Any]],
    ) -> List[TrialResult]:
        """Run trials sequentially with trial manager."""
        return self.trial_manager.run_sequential(objective_fn, configs)

    # ---- evaluation ----

    def evaluate(
        self,
        returns: List[float],
        predictions: Optional[List[float]] = None,
        targets: Optional[List[float]] = None,
    ) -> EvaluationResult:
        """Evaluate a model across multiple metrics."""
        return self.evaluator.evaluate(returns, predictions, targets)

    # ---- alpha discovery ----

    def discover_alphas(
        self,
        data: Dict[str, List[float]],
        n_candidates: int = 100,
        max_depth: int = 2,
    ) -> List[AlphaCandidate]:
        """Discover alpha factors from data."""

        def simple_eval(name: str, values: List[float]) -> Dict[str, float]:
            result = self.evaluator.evaluate(values)
            return {**result.metrics, "composite": result.composite_score}

        return self.alpha_discovery.discover(data, simple_eval, n_candidates, max_depth)

    # ---- walk-forward ----

    def walk_forward_validate(
        self,
        returns: List[float],
        eval_fn: Optional[Callable[[List[float]], Dict[str, float]]] = None,
    ) -> WalkForwardResult:
        """Run walk-forward validation."""
        if eval_fn is None:
            eval_fn = lambda r: {"sharpe": self.evaluator.sharpe_ratio(r)}
        return self.walk_forward.run_simple(returns, eval_fn)

    # ---- CV ----

    def cross_validate(
        self,
        returns: List[float],
        predictions: Optional[List[float]] = None,
        targets: Optional[List[float]] = None,
    ) -> CVResult:
        """Run time-series cross-validation."""
        return self.time_series_cv.run(returns, predictions, targets)

    # ---- leaderboard ----

    def rank_model(
        self,
        model_name: str,
        score: float,
        metrics: Optional[Dict[str, float]] = None,
        trial_id: str = "",
        scope: LeaderboardScope = LeaderboardScope.GLOBAL,
    ) -> LeaderboardEntry:
        """Add a model to the leaderboard."""
        return self.leaderboard.add_result(model_name, score, metrics, trial_id=trial_id, scope=scope)

    def champion(self, scope: Optional[LeaderboardScope] = None) -> Optional[LeaderboardEntry]:
        """Get the current champion."""
        return self.leaderboard.champion(scope)

    def top_models(self, n: int = 10) -> List[LeaderboardEntry]:
        """Get top N models."""
        return self.leaderboard.top(n)

    # ---- promotion ----

    def evaluate_promotion(
        self,
        model_name: str,
        metrics: Dict[str, float],
        has_walk_forward: bool = False,
    ) -> PromotionResult:
        """Check if a model is ready for promotion."""
        self.promotion.register(model_name)
        return self.promotion.evaluate(model_name, metrics, has_walk_forward)

    def get_promotion_stage(self, model_name: str) -> Optional[PromotionStage]:
        return self.promotion.get_stage(model_name)

    # ---- combined pipeline ----

    def run_automl_pipeline(
        self,
        objective_fn: Callable[[Dict[str, Any]], float],
        n_trials: int = 50,
        promote_best: bool = True,
    ) -> Dict[str, Any]:
        """Run full AutoML pipeline: optimize, evaluate, rank, promote.

        Args:
            objective_fn: Config -> score function.
            n_trials: Max trials.
            promote_best: Auto-promote best model.

        Returns:
            Dict with full results.
        """
        # Optimize
        opt_result = self.optimize(objective_fn, n_trials, maximize=True)

        # Rank on leaderboard
        best_entry = self.leaderboard.add_result(
            model_name=opt_result.best_config.get("model", "best_model"),
            score=opt_result.best_score,
            config=opt_result.best_config,
            metrics=opt_result.best_config.get("params", {}),
        )

        # Try promotion
        promotion_result = None
        if promote_best:
            self.promotion.register(best_entry.model_name)
            promotion_result = self.promotion.evaluate(
                best_entry.model_name,
                {"sharpe": opt_result.best_score, "ic": 0.0},
                has_walk_forward=False,
            )

        return {
            "strategy": opt_result.strategy.value,
            "best_score": opt_result.best_score,
            "best_config": opt_result.best_config,
            "total_trials": opt_result.total_trials,
            "elapsed_seconds": opt_result.elapsed_seconds,
            "leaderboard_rank": best_entry.rank,
            "leaderboard_champion": self.leaderboard.champion().model_name if self.leaderboard.champion() else None,
            "promotion": promotion_result.promoted if promotion_result else False,
            "promotion_stage": self.promotion.get_stage(best_entry.model_name).value if self.promotion.get_stage(best_entry.model_name) else None,
        }
