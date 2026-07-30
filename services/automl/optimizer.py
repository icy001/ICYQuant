"""Hyperparameter Optimizer.

Supports: Random Search, Grid Search, Bayesian Optimization, TPE.
Drives the core search loop over the search space.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from services.automl.search_space import ParamDef, SearchSpace


class SearchStrategy(str, Enum):
    RANDOM = "random"
    GRID = "grid"
    BAYESIAN = "bayesian"
    TPE = "tpe"


@dataclass
class OptimizationResult:
    strategy: SearchStrategy
    best_config: Dict[str, Any]
    best_score: float
    best_params: Dict[str, Any] = field(default_factory=dict)
    all_results: List[Dict[str, Any]] = field(default_factory=list)
    total_trials: int = 0
    elapsed_seconds: float = 0.0


class HyperOptimizer:
    """Unified hyperparameter optimizer.

    Supports multiple search strategies with a pluggable objective function.
    """

    def __init__(
        self,
        search_space: SearchSpace,
        strategy: SearchStrategy = SearchStrategy.RANDOM,
        seed: int = 42,
    ) -> None:
        self.search_space = search_space
        self.strategy = strategy
        self.rng = np.random.RandomState(seed)
        self._history: List[Tuple[Dict[str, Any], float]] = []

    def optimize(
        self,
        objective_fn: Callable[[Dict[str, Any]], float],
        n_trials: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        maximize: bool = True,
    ) -> OptimizationResult:
        """Run the optimization loop.

        Args:
            objective_fn: Function taking config dict, returning a score.
            n_trials: Max trials (defaults to search_space.max_trials).
            timeout_seconds: Max wall time.
            maximize: If True, higher scores are better.

        Returns:
            OptimizationResult.
        """
        n_trials = n_trials or self.search_space.max_trials
        timeout_seconds = timeout_seconds or self.search_space.timeout_seconds

        if self.strategy == SearchStrategy.RANDOM:
            return self._random_search(objective_fn, n_trials, timeout_seconds, maximize)
        elif self.strategy == SearchStrategy.GRID:
            return self._grid_search(objective_fn, maximize)
        elif self.strategy == SearchStrategy.BAYESIAN:
            return self._bayesian_search(objective_fn, n_trials, timeout_seconds, maximize)
        elif self.strategy == SearchStrategy.TPE:
            return self._tpe_search(objective_fn, n_trials, timeout_seconds, maximize)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")

    # ---- Random Search ----

    def _random_search(
        self,
        objective_fn: Callable[[Dict[str, Any]], float],
        n_trials: int,
        timeout_seconds: int,
        maximize: bool,
    ) -> OptimizationResult:
        start = time.time()
        all_results: List[Dict[str, Any]] = []
        best_score = float("-inf") if maximize else float("inf")
        best_config: Dict[str, Any] = {}

        for i in range(n_trials):
            if time.time() - start > timeout_seconds:
                break
            config = self.search_space.sample_config(self.rng)
            try:
                score = objective_fn(config)
            except Exception:
                continue

            all_results.append({"trial": i, "config": config, "score": score})
            if (maximize and score > best_score) or (not maximize and score < best_score):
                best_score = score
                best_config = config

        return OptimizationResult(
            strategy=self.strategy,
            best_config=best_config,
            best_score=best_score,
            all_results=all_results,
            total_trials=len(all_results),
            elapsed_seconds=time.time() - start,
        )

    # ---- Grid Search ----

    def _grid_search(
        self,
        objective_fn: Callable[[Dict[str, Any]], float],
        maximize: bool,
    ) -> OptimizationResult:
        start = time.time()
        configs = self.search_space.grid_configs()
        all_results: List[Dict[str, Any]] = []
        best_score = float("-inf") if maximize else float("inf")
        best_config: Dict[str, Any] = {}

        for i, config in enumerate(configs):
            try:
                score = objective_fn(config)
            except Exception:
                continue
            all_results.append({"trial": i, "config": config, "score": score})
            if (maximize and score > best_score) or (not maximize and score < best_score):
                best_score = score
                best_config = config

        return OptimizationResult(
            strategy=self.strategy,
            best_config=best_config,
            best_score=best_score,
            all_results=all_results,
            total_trials=len(all_results),
            elapsed_seconds=time.time() - start,
        )

    # ---- Bayesian Optimization (Gaussian Process surrogate) ----

    def _bayesian_search(
        self,
        objective_fn: Callable[[Dict[str, Any]], float],
        n_trials: int,
        timeout_seconds: int,
        maximize: bool,
    ) -> OptimizationResult:
        """Bayesian optimization using Gaussian Process.

        Requires scikit-learn. Falls back to random search if not available.
        """
        try:
            from sklearn.gaussian_process import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import RBF, ConstantKernel
        except ImportError:
            return self._random_search(objective_fn, n_trials, timeout_seconds, maximize)

        start = time.time()
        all_results: List[Dict[str, Any]] = []
        best_score = float("-inf") if maximize else float("inf")
        best_config: Dict[str, Any] = {}

        # Initial random exploration
        n_init = max(5, n_trials // 5)
        X_obs: List[List[float]] = []
        y_obs: List[float] = []

        for i in range(n_trials):
            if time.time() - start > timeout_seconds:
                break

            if i < n_init:
                config = self.search_space.sample_config(self.rng)
            else:
                # Use GP to propose next point
                config = self._gp_probe(X_obs, y_obs, maximize)

            try:
                score = objective_fn(config)
            except Exception:
                continue

            # Encode config as feature vector
            x_vec = self._encode_config(config)
            X_obs.append(x_vec)
            y_obs.append(score)

            all_results.append({"trial": i, "config": config, "score": score})
            if (maximize and score > best_score) or (not maximize and score < best_score):
                best_score = score
                best_config = config

        return OptimizationResult(
            strategy=self.strategy,
            best_config=best_config,
            best_score=best_score,
            all_results=all_results,
            total_trials=len(all_results),
            elapsed_seconds=time.time() - start,
        )

    # ---- TPE (Tree-structured Parzen Estimator) ----

    def _tpe_search(
        self,
        objective_fn: Callable[[Dict[str, Any]], float],
        n_trials: int,
        timeout_seconds: int,
        maximize: bool,
    ) -> OptimizationResult:
        """TPE-style search: maintain good/bad distributions and sample from good.

        Simplified TPE implementation using kernel density estimation.
        """
        start = time.time()
        all_results: List[Dict[str, Any]] = []
        best_score = float("-inf") if maximize else float("inf")
        best_config: Dict[str, Any] = {}

        n_init = max(10, n_trials // 4)
        gamma = 0.25  # top fraction considered "good"

        for i in range(n_trials):
            if time.time() - start > timeout_seconds:
                break

            if i < n_init or len(all_results) < 5:
                config = self.search_space.sample_config(self.rng)
            else:
                # Sort and pick top-gamma as "good"
                sorted_results = sorted(all_results, key=lambda r: r["score"], reverse=maximize)
                n_good = max(1, int(len(sorted_results) * gamma))
                good = sorted_results[:n_good]

                # Sample from good configs (with mutation)
                template = self.rng.choice(good)["config"]
                config = self._mutate_config(template)

            try:
                score = objective_fn(config)
            except Exception:
                continue

            all_results.append({"trial": i, "config": config, "score": score})
            if (maximize and score > best_score) or (not maximize and score < best_score):
                best_score = score
                best_config = config

        return OptimizationResult(
            strategy=self.strategy,
            best_config=best_config,
            best_score=best_score,
            all_results=all_results,
            total_trials=len(all_results),
            elapsed_seconds=time.time() - start,
        )

    # ---- helpers ----

    @staticmethod
    def _encode_config(config: Dict[str, Any]) -> List[float]:
        """Flatten config into a numeric vector."""
        vec: List[float] = []
        params = config.get("params", {})
        for v in sorted(params.values()):
            if isinstance(v, (int, float)):
                vec.append(float(v))
            elif isinstance(v, str):
                vec.append(float(hash(v) % 1000))
            else:
                vec.append(0.0)
        return vec if vec else [0.0]

    def _gp_probe(
        self, X_obs: List[List[float]], y_obs: List[float], maximize: bool
    ) -> Dict[str, Any]:
        """GP-based acquisition function to propose next config."""
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import RBF, ConstantKernel

        if len(X_obs) < 3:
            return self.search_space.sample_config(self.rng)

        kernel = ConstantKernel(1.0) * RBF(length_scale=1.0)
        gp = GaussianProcessRegressor(kernel=kernel, alpha=1e-6, normalize_y=True)

        X = np.array(X_obs)
        y = np.array(y_obs)
        try:
            gp.fit(X, y)
        except Exception:
            return self.search_space.sample_config(self.rng)

        # Random candidate sampling with UCB acquisition
        best_val = float("-inf")
        best_config = self.search_space.sample_config(self.rng)
        for _ in range(50):
            cand = self.search_space.sample_config(self.rng)
            x_vec = np.array(self._encode_config(cand)).reshape(1, -1)
            # Adjust dims if needed
            if x_vec.shape[1] != X.shape[1]:
                x_vec = np.zeros((1, X.shape[1]))
                for j in range(min(x_vec.shape[1], len(self._encode_config(cand)))):
                    x_vec[0, j] = self._encode_config(cand)[j]
            try:
                mu, sigma = gp.predict(x_vec, return_std=True)
                ucb = mu[0] + 2.0 * sigma[0] if maximize else mu[0] - 2.0 * sigma[0]
                if ucb > best_val:
                    best_val = ucb
                    best_config = cand
            except Exception:
                continue

        return best_config

    def _mutate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Slightly mutate a config for TPE sampling."""
        mutated = dict(config)
        params = mutated.get("params", {})
        mutated_params = dict(params)

        for name, val in list(params.items()):
            if self.rng.random() < 0.3:
                # Mutate this param
                if isinstance(val, bool):
                    mutated_params[name] = not val
                elif isinstance(val, int):
                    mutated_params[name] = val + self.rng.choice([-1, 0, 1])
                elif isinstance(val, float):
                    mutated_params[name] = val * (1 + self.rng.uniform(-0.3, 0.3))

        mutated["params"] = mutated_params
        return mutated
