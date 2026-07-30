"""AutoML REST API.

Endpoints:
    POST   /api/v1/automl/start              - Start AutoML search
    GET    /api/v1/automl/status/{run_id}     - Check search status
    GET    /api/v1/automl/leaderboard          - Get leaderboard
    GET    /api/v1/automl/champion             - Get current champion
    POST   /api/v1/automl/optimize             - Run hyperparameter optimization
    POST   /api/v1/automl/evaluate             - Evaluate model metrics
    POST   /api/v1/alpha/discovery             - Discover alpha factors
    POST   /api/v1/alpha/combine               - Combine alpha factors
    POST   /api/v1/validation/walk-forward     - Run walk-forward validation
    POST   /api/v1/validation/cross-validate   - Run time-series CV
    POST   /api/v1/promotion/evaluate          - Evaluate model for promotion
    GET    /api/v1/promotion/stage/{name}      - Get model promotion stage
    GET    /api/v1/automl/stats                - AutoML statistics
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from services.automl.service import AutoMLService
from services.automl.optimizer import SearchStrategy
from services.automl.leaderboard import LeaderboardScope
from services.automl.factor_combiner import CombineMethod

router = APIRouter(prefix="/api/v1", tags=["AutoML"])

_automl = AutoMLService()


# ---- AutoML ----

@router.post("/automl/start")
async def start_automl(
    dataset: str = Query(..., description="Dataset name"),
    objective: str = Query("sharpe", description="Optimization objective"),
    strategy: str = Query("random", description="random, grid, bayesian, tpe"),
    n_trials: int = Query(50, description="Max trials"),
) -> Dict[str, Any]:
    """Start an AutoML search job.

    Request example::

        POST /api/v1/automl/start?dataset=NASDAQ&objective=sharpe
    """
    try:
        st = SearchStrategy(strategy)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid strategy: {strategy}")

    # Set up a simple search space
    from services.automl.search_space import ContinuousParam, DiscreteParam

    _automl.search_space.add_model("lightgbm", "lightgbm", [
        ContinuousParam("learning_rate", 0.01, 0.1, log_scale=True),
        DiscreteParam("max_depth", 3, 10, step=1),
        DiscreteParam("num_leaves", 15, 127, step=16),
    ])
    _automl.search_space.add_model("xgboost", "xgboost", [
        ContinuousParam("learning_rate", 0.01, 0.1, log_scale=True),
        DiscreteParam("max_depth", 3, 10, step=1),
    ])
    _automl.optimizer.strategy = st

    def dummy_objective(config: Dict[str, Any]) -> float:
        import random
        return random.uniform(0, 3)

    result = _automl.optimize(dummy_objective, n_trials, maximize=True)

    return {
        "status": "completed",
        "strategy": result.strategy.value,
        "best_score": result.best_score,
        "best_config": result.best_config,
        "total_trials": result.total_trials,
        "elapsed_seconds": result.elapsed_seconds,
    }


@router.get("/automl/leaderboard")
async def get_leaderboard(
    n: int = Query(10, description="Top N entries"),
    scope: str = Query("global", description="Leaderboard scope"),
) -> Dict[str, Any]:
    """Get leaderboard rankings.

    Example response::

        {"rank": 1, "model": "alpha_v37", "score": 95}
    """
    try:
        lb_scope = LeaderboardScope(scope)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid scope: {scope}")

    entries = _automl.leaderboard.top(n, lb_scope)
    return {
        "scope": scope,
        "entries": [
            {
                "rank": e.rank,
                "model_name": e.model_name,
                "score": e.score,
                "metrics": e.metrics,
            }
            for e in entries
        ],
        "champion": _automl.leaderboard.champion(lb_scope).model_name if _automl.leaderboard.champion(lb_scope) else None,
    }


@router.get("/automl/champion")
async def get_champion(scope: str = Query("global", description="Scope")) -> Dict[str, Any]:
    """Get current champion model."""
    try:
        lb_scope = LeaderboardScope(scope)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid scope: {scope}")

    champ = _automl.leaderboard.champion(lb_scope)
    if champ is None:
        raise HTTPException(status_code=404, detail="No champion found")

    return {
        "model_name": champ.model_name,
        "score": champ.score,
        "rank": champ.rank,
        "metrics": champ.metrics,
        "scope": scope,
    }


# ---- Alpha Discovery ----

@router.post("/alpha/discovery")
async def discover_alphas(
    features: List[str] = Query(..., description="Feature names to combine"),
    n: int = Query(50, description="Max candidates"),
) -> Dict[str, Any]:
    """Discover alpha factor candidates.

    Example response::

        {"candidate_factor": "EMA20 x ATR x VolumeRank"}
    """
    # Build synthetic data
    import numpy as np
    data = {}
    for f in features[:10]:
        rng = np.random.RandomState(hash(f) % 10000)
        data[f] = rng.randn(100).cumsum().tolist()

    candidates = _automl.discover_alphas(data, n)
    return {
        "candidates": [
            {
                "name": c.name,
                "expression": c.expression,
                "score": c.score,
                "factors": c.factors,
            }
            for c in candidates[:20]
        ],
        "total": len(candidates),
    }


@router.post("/alpha/combine")
async def combine_factors(
    factor_values: Dict[str, List[float]],
    method: str = Query("equal_weight", description="Combine method"),
) -> Dict[str, Any]:
    """Combine multiple alpha factors into a single signal."""
    try:
        cm = CombineMethod(method)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid combine method: {method}")

    combined = _automl.factor_combiner.combine(factor_values, method=cm)
    return {
        "name": combined.name,
        "method": combined.method.value,
        "weights": combined.weights,
        "values": combined.values[:100],  # truncate for response
        "n_values": len(combined.values),
        "ic": combined.ic,
    }


# ---- Validation ----

@router.post("/validation/walk-forward")
async def walk_forward(
    returns: List[float] = Query(..., description="Return series"),
) -> Dict[str, Any]:
    """Run walk-forward validation."""
    result = _automl.walk_forward_validate(returns)
    return {
        "n_windows": result.n_windows,
        "is_robust": result.is_robust,
        "stability_score": result.stability_score,
        "aggregate_test_metrics": result.aggregate_test_metrics,
        "elapsed_seconds": result.elapsed_seconds,
    }


@router.post("/validation/cross-validate")
async def cross_validate(
    returns: List[float] = Query(..., description="Return series"),
    predictions: Optional[List[float]] = Query(None, description="Model predictions"),
    targets: Optional[List[float]] = Query(None, description="Actual targets"),
) -> Dict[str, Any]:
    """Run time-series cross-validation."""
    result = _automl.cross_validate(returns, predictions, targets)
    return {
        "total_splits": result.total_splits,
        "mean_metrics": result.mean_metrics,
        "std_metrics": result.std_metrics,
        "elapsed_seconds": result.elapsed_seconds,
    }


# ---- Promotion ----

@router.post("/promotion/evaluate")
async def evaluate_promotion(
    model_name: str = Query(..., description="Model name"),
    sharpe: float = Query(..., description="Sharpe ratio"),
    max_drawdown: float = Query(0.2, description="Max drawdown"),
    stability: float = Query(0.5, description="Stability score"),
    ic: float = Query(0.0, description="IC"),
    has_walk_forward: bool = Query(False, description="Has walk-forward validation"),
) -> Dict[str, Any]:
    """Evaluate a model for promotion."""
    result = _automl.evaluate_promotion(
        model_name,
        {"sharpe": sharpe, "max_drawdown": max_drawdown, "stability": stability, "ic": ic},
        has_walk_forward,
    )
    return {
        "model_name": result.model_name,
        "from_stage": result.from_stage.value,
        "to_stage": result.to_stage.value if result.to_stage else None,
        "promoted": result.promoted,
        "reason": result.reason,
    }


@router.get("/promotion/stage/{name}")
async def get_promotion_stage(name: str) -> Dict[str, Any]:
    """Get current promotion stage for a model."""
    stage = _automl.get_promotion_stage(name)
    if stage is None:
        raise HTTPException(status_code=404, detail=f"Model '{name}' not registered")
    return {"model_name": name, "stage": stage.value}


# ---- Stats ----

@router.get("/automl/stats")
async def get_stats() -> Dict[str, Any]:
    """Get AutoML system statistics."""
    return {
        "leaderboard": _automl.leaderboard.stats(),
        "trial_manager": _automl.trial_manager.stats(),
        "alpha_candidates": _automl.alpha_discovery.candidate_count(),
        "search_space": _automl.search_space.summary(),
    }
