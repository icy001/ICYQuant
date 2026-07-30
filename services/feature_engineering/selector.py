"""Feature Selector.

Automated feature selection from high-dimensional feature spaces.
Supports variance filtering, correlation filtering, mutual information,
recursive feature elimination, and tree-based importance selection.

Usage::

    from services.feature_engineering import FeatureSelector, VarianceFilter

    selector = FeatureSelector()
    selector.add_filter(VarianceFilter(threshold=0.01))
    selector.add_filter(CorrelationFilter(threshold=0.95))
    selected = selector.select(feature_matrix, feature_names)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np


@dataclass
class SelectionReport:
    """Report of feature selection results."""

    selected_features: List[str]
    removed_features: List[str]
    filter_results: Dict[str, List[str]] = field(default_factory=dict)
    original_count: int = 0
    selected_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"SelectionReport(original={self.original_count}, "
            f"selected={self.selected_count}, "
            f"removed={len(self.removed_features)})"
        )


# ---- Base filter ----

class BaseFilter:
    """Abstract base for feature selection filters."""

    name: str = "base"

    def select(
        self,
        X: np.ndarray,
        feature_names: List[str],
        y: Optional[np.ndarray] = None,
    ) -> Tuple[List[str], List[str]]:
        """Return (selected_names, removed_names)."""
        raise NotImplementedError


# ---- Variance Filter ----

class VarianceFilter(BaseFilter):
    """Remove features with variance below threshold.

    Args:
        threshold: Minimum variance to keep a feature.
    """

    name = "variance"

    def __init__(self, threshold: float = 0.0) -> None:
        self.threshold = threshold

    def select(
        self,
        X: np.ndarray,
        feature_names: List[str],
        y: Optional[np.ndarray] = None,
    ) -> Tuple[List[str], List[str]]:
        if X.shape[0] <= 1:
            return (list(feature_names), [])
        var = np.nanvar(X, axis=0)
        selected = [feature_names[i] for i in range(len(feature_names)) if var[i] > self.threshold]
        removed = [f for f in feature_names if f not in selected]
        return (selected, removed)


# ---- Correlation Filter ----

class CorrelationFilter(BaseFilter):
    """Remove one of each pair of highly correlated features.

    Args:
        threshold: Correlation coefficient above which to drop one feature.
        method: "pearson" or "spearman".
        keep: Strategy: "first" keeps the first in list order.
    """

    name = "correlation"

    def __init__(self, threshold: float = 0.95, method: str = "pearson", keep: str = "first") -> None:
        self.threshold = threshold
        self.method = method
        self.keep = keep

    def select(
        self,
        X: np.ndarray,
        feature_names: List[str],
        y: Optional[np.ndarray] = None,
    ) -> Tuple[List[str], List[str]]:
        n_features = X.shape[1]
        if n_features <= 1:
            return (list(feature_names), [])

        # Compute correlation matrix
        if self.method == "spearman":
            from scipy.stats import rankdata
            X_ranked = np.apply_along_axis(rankdata, 0, X)
            corr = np.corrcoef(X_ranked, rowvar=False)
        else:
            corr = np.corrcoef(X, rowvar=False)

        corr = np.nan_to_num(corr, nan=0.0)
        # Make upper triangle (excluding diagonal)
        upper = np.triu(np.abs(corr), k=1)

        to_remove: Set[int] = set()
        for i in range(n_features):
            for j in range(i + 1, n_features):
                if upper[i, j] > self.threshold:
                    # Remove the one later in the list
                    to_remove.add(j)

        removed_names = [feature_names[i] for i in sorted(to_remove)]
        selected_names = [f for f in feature_names if f not in removed_names]
        return (selected_names, removed_names)


# ---- Mutual Information Filter ----

class MutualInfoFilter(BaseFilter):
    """Keep top-k features by mutual information with target.

    Args:
        k: Number of features to keep.
        n_bins: Number of bins for discretization.
    """

    name = "mutual_info"

    def __init__(self, k: int = 50, n_bins: int = 20) -> None:
        self.k = k
        self.n_bins = n_bins

    def select(
        self,
        X: np.ndarray,
        feature_names: List[str],
        y: Optional[np.ndarray] = None,
    ) -> Tuple[List[str], List[str]]:
        if y is None or X.shape[1] <= self.k:
            return (list(feature_names), [])

        mi_scores = self._compute_mi(X, y)
        # Keep top-k
        indices = np.argsort(mi_scores)[::-1][: self.k]
        selected = [feature_names[i] for i in indices]
        removed = [f for f in feature_names if f not in selected]
        return (selected, removed)

    def _compute_mi(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Compute mutual information for each feature with y."""
        n_features = X.shape[1]
        scores = np.zeros(n_features)

        # Discretize y
        y_bins = self._digitize(y)

        for i in range(n_features):
            col = X[:, i]
            mask = ~np.isnan(col)
            if mask.sum() < 2:
                scores[i] = 0.0
                continue
            x_bins = self._digitize(col[mask])
            y_masked = y_bins[mask]
            scores[i] = self._mutual_info_score(x_bins, y_masked)

        return scores

    def _digitize(self, arr: np.ndarray) -> np.ndarray:
        """Discretize a 1D array into bins."""
        clean = arr[~np.isnan(arr)]
        if len(clean) < 2:
            return np.zeros_like(arr, dtype=int)
        percentiles = np.linspace(0, 100, self.n_bins + 1)[1:-1]
        edges = np.percentile(clean, percentiles)
        edges = np.unique(edges)
        if len(edges) < 2:
            return np.zeros_like(arr, dtype=int)
        return np.digitize(arr, edges)

    @staticmethod
    def _mutual_info_score(x: np.ndarray, y: np.ndarray) -> float:
        """Compute mutual information between two discrete arrays."""
        from collections import Counter

        n = len(x)
        if n == 0:
            return 0.0

        xy_pairs = list(zip(x, y))
        joint = Counter(xy_pairs)
        marginal_x = Counter(x)
        marginal_y = Counter(y)

        mi = 0.0
        for (xv, yv), count in joint.items():
            p_xy = count / n
            p_x = marginal_x[xv] / n
            p_y = marginal_y[yv] / n
            mi += p_xy * np.log(p_xy / (p_x * p_y))

        return float(mi)


# ---- RFE Filter ----

class RFEliminator(BaseFilter):
    """Recursive Feature Elimination using a provided model.

    Args:
        n_features_to_select: Target number of features.
        step: Number of features to remove per iteration.
        model_factory: Callable returning a model with fit/coef_ or feature_importances_.
    """

    name = "rfe"

    def __init__(
        self,
        n_features_to_select: int = 50,
        step: int = 5,
        model_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.n_features_to_select = n_features_to_select
        self.step = step
        self.model_factory = model_factory

    def select(
        self,
        X: np.ndarray,
        feature_names: List[str],
        y: Optional[np.ndarray] = None,
    ) -> Tuple[List[str], List[str]]:
        if y is None or X.shape[1] <= self.n_features_to_select:
            return (list(feature_names), [])

        X_clean = np.nan_to_num(X, nan=0.0)

        if self.model_factory is None:
            # Use simple linear model
            from sklearn.linear_model import Ridge
            model = Ridge(alpha=1.0)
        else:
            model = self.model_factory()

        remaining = list(range(X.shape[1]))

        while len(remaining) > self.n_features_to_select:
            model.fit(X_clean[:, remaining], y)
            if hasattr(model, "coef_"):
                importances = np.abs(model.coef_.ravel())
            elif hasattr(model, "feature_importances_"):
                importances = np.abs(model.feature_importances_)
            else:
                break

            n_to_remove = min(self.step, len(remaining) - self.n_features_to_select)
            if n_to_remove <= 0:
                break

            # Remove least important features
            indices = np.argsort(importances)[:n_to_remove]
            for idx in sorted(indices, reverse=True):
                remaining.pop(idx)

        selected = [feature_names[i] for i in remaining]
        removed = [f for f in feature_names if f not in selected]
        return (selected, removed)


# ---- Tree Importance Filter ----

class TreeImportanceFilter(BaseFilter):
    """Keep top-k features by tree-based feature importance.

    Args:
        k: Number of features to keep.
        n_estimators: Number of trees.
    """

    name = "tree_importance"

    def __init__(self, k: int = 50, n_estimators: int = 100) -> None:
        self.k = k
        self.n_estimators = n_estimators

    def select(
        self,
        X: np.ndarray,
        feature_names: List[str],
        y: Optional[np.ndarray] = None,
    ) -> Tuple[List[str], List[str]]:
        if y is None or X.shape[1] <= self.k:
            return (list(feature_names), [])

        X_clean = np.nan_to_num(X, nan=0.0)
        y_clean = np.nan_to_num(y, nan=0.0)

        from sklearn.ensemble import ExtraTreesClassifier
        model = ExtraTreesClassifier(
            n_estimators=self.n_estimators,
            max_depth=10,
            random_state=42,
            n_jobs=-1,
        )

        # If y is continuous, use regression version
        if len(np.unique(y_clean)) > 20:
            from sklearn.ensemble import ExtraTreesRegressor
            model = ExtraTreesRegressor(
                n_estimators=self.n_estimators,
                max_depth=10,
                random_state=42,
                n_jobs=-1,
            )

        model.fit(X_clean, y_clean)
        importances = model.feature_importances_
        indices = np.argsort(importances)[::-1][: self.k]

        selected = [feature_names[i] for i in indices]
        removed = [f for f in feature_names if f not in selected]
        return (selected, removed)


# ---- Feature Selector Orchestrator ----

class FeatureSelector:
    """Orchestrate multiple selection filters in sequence.

    Example::

        selector = FeatureSelector()
        selector.add_filter(VarianceFilter(threshold=0.01))
        selector.add_filter(CorrelationFilter(threshold=0.95))
        selector.add_filter(MutualInfoFilter(k=100))
        report = selector.select(X, feature_names, y)
    """

    def __init__(self) -> None:
        self._filters: List[BaseFilter] = []

    def add_filter(self, f: BaseFilter) -> None:
        """Add a selection filter to the pipeline."""
        self._filters.append(f)

    def remove_filter(self, name: str) -> None:
        """Remove a filter by name."""
        self._filters = [f for f in self._filters if f.name != name]

    def select(
        self,
        X: np.ndarray,
        feature_names: List[str],
        y: Optional[np.ndarray] = None,
    ) -> SelectionReport:
        """Apply all filters sequentially and return a report.

        Args:
            X: Feature matrix (n_samples, n_features).
            feature_names: List of feature names.
            y: Target array (optional, required for supervised filters).

        Returns:
            SelectionReport with selected and removed features.
        """
        original_count = len(feature_names)
        current_names = list(feature_names)
        filter_results: Dict[str, List[str]] = {}

        for f in self._filters:
            # Build current X subset
            indices = [feature_names.index(n) for n in current_names]
            X_sub = X[:, indices]
            selected, removed = f.select(X_sub, current_names, y)
            filter_results[f.name] = removed
            current_names = selected

        removed_features = [f for f in feature_names if f not in current_names]
        return SelectionReport(
            selected_features=current_names,
            removed_features=removed_features,
            filter_results=filter_results,
            original_count=original_count,
            selected_count=len(current_names),
        )
